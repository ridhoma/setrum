import os
import requests
import pandas as pd
from datetime import timedelta
from core.credentials import get_octopus_account_number, get_octopus_api_key
from core.database import get_connection, upsert_dataframe
from core.queries import (
    finish_process_log,
    get_job_state,
    start_process_log,
    update_job_status,
)
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.octopus.energy/v1"

def get_auth():
    api_key = get_octopus_api_key()
    if not api_key:
        raise ValueError("API Key is missing. Set OCTOPUS_API_KEY in .env or store it in macOS Keychain.")
    return (api_key, '')

def _fetch_paginated_chunk(url, period_from, period_to):
    rt = pd.to_datetime(period_to, utc=True).strftime('%Y-%m-%dT%H:%M:%SZ')
    rf = pd.to_datetime(period_from, utc=True).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    params = {'period_from': rf, 'period_to': rt, 'page_size': 25000}
    results = []
    next_url = url
    
    while next_url:
        resp_params = params if next_url == url else None
        response = requests.get(next_url, auth=get_auth(), params=resp_params, timeout=20)
        
        if response.status_code != 200:
            print(f"API Error {response.status_code}: {response.text}")
            raise Exception(f"Failed to fetch: HTTP {response.status_code}")
            
        data = response.json()
        results.extend(data.get('results', []))
        next_url = data.get('next')
        
    return results

def _chunked_fetch(endpoint_name, fetch_url, start_date, end_date, formatter_func, db_table, conflict_cols):
    if db_table == 'source_consumptions':
        process_type = 'FETCH_CONSUMPTIONS'
    elif db_table == 'source_electricity_standard_unit_rates':
        process_type = 'FETCH_UNIT_RATES'
    elif db_table == 'source_electricity_standing_charges':
        process_type = 'FETCH_STANDING_CHARGES'
    else:
        process_type = 'FETCH_API'

    update_job_status(endpoint_name, 'RUNNING')
    total_rows = 0
    chunks_count = 0
    start_str = str(start_date)[:16]
    end_str = str(end_date)[:16]
    log_id, t0 = start_process_log(
        process_type,
        endpoint_name,
        target_table=db_table,
        details=f"Fetching window {start_str} → {end_str}…",
    )
    try:
        current_start = pd.to_datetime(start_date, utc=True)
        final_end = pd.to_datetime(end_date, utc=True)
        start_fmt = current_start.strftime('%Y-%m-%d')
        end_fmt = final_end.strftime('%Y-%m-%d')
        
        if (final_end - current_start).total_seconds() < 60:
            update_job_status(endpoint_name, 'SUCCESS')
            finish_process_log(
                log_id,
                t0,
                status='SKIPPED',
                rows_affected=0,
                details=f"Already up to date ({start_fmt} → {end_fmt})",
            )
            print(f"✅ [{endpoint_name}] Already up to date.")
            return
            
        is_tariff_table = db_table in (
            'source_electricity_standard_unit_rates',
            'source_electricity_standing_charges',
        )
        step_days = 90 if is_tariff_table else 30

        while current_start < final_end:
            chunk_end = min(current_start + timedelta(days=step_days), final_end)
            chunks_count += 1
            
            print(f"[{endpoint_name}] Syncing {current_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}...")
            results = _fetch_paginated_chunk(fetch_url, current_start, chunk_end)
            
            if results:
                df = formatter_func(results)
                total_rows += len(df)
                with get_connection() as conn:
                    upsert_dataframe(conn, df, db_table, conflict_cols)
                    
                max_ts = df['interval_start'].max()
                if is_tariff_table:
                    chunk_end_iso = chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ')
                    if chunk_end_iso > str(max_ts):
                        max_ts = chunk_end_iso
                min_ts = df['interval_start'].min()
                
                state = get_job_state(endpoint_name)
                newest = state.get('last_successful_timestamp')
                oldest = state.get('oldest_successful_timestamp')
                
                if not newest or max_ts > newest:
                    newest = max_ts
                if not oldest or min_ts < oldest:
                    oldest = min_ts
                    
                update_job_status(endpoint_name, 'RUNNING', newest, oldest)
            
            current_start = chunk_end
        
        update_job_status(endpoint_name, 'SUCCESS')
        if total_rows > 0:
            summary_msg = f"Upserted {total_rows:,} records across {chunks_count} chunk(s) ({start_fmt} → {end_fmt})"
        else:
            summary_msg = f"Checked {start_fmt} → {end_fmt} (0 new records available from Octopus API)"
        finish_process_log(log_id, t0, status='SUCCESS', rows_affected=total_rows, details=summary_msg)
        print(f"✅ [{endpoint_name}] Catch-up Process Complete.")
    
    except Exception as e:
        update_job_status(endpoint_name, f'ERROR: {str(e)}')
        finish_process_log(
            log_id,
            t0,
            status='ERROR',
            rows_affected=total_rows,
            details=f"Failed ({start_str[:10]} → {end_str[:10]}): {str(e)}",
        )
        print(f"❌ [{endpoint_name}] Sync Failed: {e}")

def fetch_consumptions(start_date, end_date, mpan, serial_number):
    def format_consumptions(results):
        df = pd.DataFrame(results)
        df['interval_start'] = pd.to_datetime(df['interval_start'], utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        df['interval_end'] = pd.to_datetime(df['interval_end'], utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        if 'consumption' in df.columns:
            df = df.rename(columns={'consumption': 'consumption_kwh'})
        df['mpan'] = mpan
        df['meter_serial_number'] = serial_number
        return df[['interval_start', 'interval_end', 'consumption_kwh', 'mpan', 'meter_serial_number']]
        
    endpoint = f"consumptions_{mpan}_{serial_number}"
    url = f"{BASE_URL}/electricity-meter-points/{mpan}/meters/{serial_number}/consumption/"
    _chunked_fetch(endpoint, url, start_date, end_date, format_consumptions, 'source_consumptions', ['interval_start', 'mpan', 'meter_serial_number'])

def extract_product_code(tariff_code):
    parts = tariff_code.split('-')
    if len(parts) < 4: return None
    return "-".join(parts[2:-1])

def fetch_tariff_pricing(start_date, end_date, tariff_code):
    product_code = extract_product_code(tariff_code)
    if not product_code:
        print(f"⚠️ Could not extract product code from {tariff_code}")
        return
        
    self_auth = get_auth()
    
    print(f"[{product_code}] Synchronizing Product Detail...")
    update_job_status(f'product_{product_code}', 'RUNNING')
    prod_log_id, prod_t0 = start_process_log(
        'FETCH_PRODUCT',
        f'product_{product_code}',
        target_table='source_products',
        details=f"Synchronizing product catalog metadata for {product_code}…",
    )
    try:
        prod_resp = requests.get(f"{BASE_URL}/products/{product_code}/", timeout=20)
        if prod_resp.status_code == 200:
            p = prod_resp.json()
            df_prod = pd.DataFrame([{
                'product_code': p.get('code'),
                'full_name': p.get('full_name'),
                'description': p.get('description'),
                'brand': p.get('brand')
            }])
            with get_connection() as conn:
                upsert_dataframe(conn, df_prod, 'source_products', ['product_code'])
            update_job_status(f'product_{product_code}', 'SUCCESS')
            finish_process_log(
                prod_log_id,
                prod_t0,
                status='SUCCESS',
                rows_affected=1,
                details=f"Saved product metadata for {product_code} ({p.get('full_name') or 'Octopus Product'})",
            )
            print(f"✅ [{product_code}] Core Product Catalog Saved")
        else:
            err_msg = f"HTTP {prod_resp.status_code} fetching product {product_code}"
            update_job_status(f'product_{product_code}', f'ERROR: {err_msg}')
            finish_process_log(prod_log_id, prod_t0, status='ERROR', rows_affected=0, details=err_msg)
    except Exception as e:
        update_job_status(f'product_{product_code}', f'ERROR: {str(e)}')
        finish_process_log(
            prod_log_id,
            prod_t0,
            status='ERROR',
            rows_affected=0,
            details=f"Product fetch failed for {product_code}: {str(e)}",
        )
        
    def format_rates(results):
        df = pd.DataFrame(results)
        if df.empty: return df
        df['interval_start'] = pd.to_datetime(df['valid_from'], utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        if 'valid_to' in df.columns:
            df['interval_end'] = pd.to_datetime(df['valid_to'].fillna(pd.Timestamp('now', tz='UTC')), utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            df['interval_end'] = None
        df['tariff_code'] = tariff_code
        return df[['interval_start', 'interval_end', 'value_inc_vat', 'value_exc_vat', 'tariff_code']]
        
    rates_url = f"{BASE_URL}/products/{product_code}/electricity-tariffs/{tariff_code}/standard-unit-rates/"
    charges_url = f"{BASE_URL}/products/{product_code}/electricity-tariffs/{tariff_code}/standing-charges/"
    
    print(f"[pricing_{tariff_code}] Firing Async Parallel Sync...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_rates = executor.submit(_chunked_fetch, 
            f'unit_rates_{tariff_code}', rates_url, start_date, end_date, 
            format_rates, 'source_electricity_standard_unit_rates', ['interval_start', 'tariff_code'])
            
        future_charges = executor.submit(_chunked_fetch, 
            f'standing_charges_{tariff_code}', charges_url, start_date, end_date, 
            format_rates, 'source_electricity_standing_charges', ['interval_start', 'tariff_code'])
        
        future_rates.result()
        future_charges.result()

def fetch_accounts():
    account_number = get_octopus_account_number()
    if not account_number:
        print("⚠️ No OCTOPUS_ACCOUNT_NUMBER found in .env or macOS Keychain. Skipping account fetch.")
        return

    update_job_status('accounts', 'RUNNING')
    acc_log_id, acc_t0 = start_process_log(
        'FETCH_ACCOUNTS',
        'accounts',
        target_table='source_accounts, source_electricity_meters, source_electricity_agreements',
        details=f"Synchronizing Octopus account {account_number}…",
    )
    try:
        print("[accounts] Synchronizing Account Details...")
        url = f"{BASE_URL}/accounts/{account_number}/"
        response = requests.get(url, auth=get_auth(), timeout=20)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch accounts (HTTP {response.status_code})")
            
        data = response.json()
        account_number_val = data.get('number')
        
        accounts_data, meters_data, agreements_data = [], [], []
        
        for prop in data.get('properties', []):
            accounts_data.append({
                'account_number': account_number_val,
                'account_id': prop.get('id'),
                'moved_in_at': prop.get('moved_in_at'),
                'moved_out_at': prop.get('moved_out_at'),
                'address_line_1': prop.get('address_line_1'),
                'town': prop.get('town'),
                'postcode': prop.get('postcode')
            })
            
            for emp in prop.get('electricity_meter_points', []):
                mpan = emp.get('mpan')
                for meter in emp.get('meters', []):
                    meters_data.append({
                        'account_number': account_number_val,
                        'account_id': prop.get('id'),
                        'mpan': mpan,
                        'serial_number': meter.get('serial_number')
                    })
                    
                for agreement in emp.get('agreements', []):
                    agreements_data.append({
                        'account_number': account_number_val,
                        'account_id': prop.get('id'),
                        'mpan': mpan,
                        'tariff_code': agreement.get('tariff_code'),
                        'valid_from': agreement.get('valid_from'),
                        'valid_to': agreement.get('valid_to')
                    })
        
        with get_connection() as conn:
            df_accounts = pd.DataFrame(accounts_data)
            if not df_accounts.empty:
                upsert_dataframe(conn, df_accounts, 'source_accounts', ['account_number', 'account_id'])
            
            df_meters = pd.DataFrame(meters_data)
            if not df_meters.empty:
                upsert_dataframe(conn, df_meters, 'source_electricity_meters', ['account_number', 'account_id', 'mpan', 'serial_number'])
            
            df_agreements = pd.DataFrame(agreements_data)
            if not df_agreements.empty:
                upsert_dataframe(conn, df_agreements, 'source_electricity_agreements', ['account_number', 'account_id', 'mpan', 'tariff_code', 'valid_from'])

        total_rows = len(accounts_data) + len(meters_data) + len(agreements_data)
        update_job_status('accounts', 'SUCCESS')
        finish_process_log(
            acc_log_id,
            acc_t0,
            status='SUCCESS',
            rows_affected=total_rows,
            details=f"Upserted {len(accounts_data)} properties, {len(meters_data)} meters, {len(agreements_data)} tariff agreements",
        )
        print(f"✅ [accounts] Sync Complete")
    except Exception as e:
        update_job_status('accounts', f'ERROR: {str(e)}')
        finish_process_log(
            acc_log_id,
            acc_t0,
            status='ERROR',
            rows_affected=0,
            details=f"Account fetch failed: {str(e)}",
        )
        print(f"❌ [accounts] Sync Failed: {e}")
