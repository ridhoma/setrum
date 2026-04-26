import os
import requests
import pandas as pd
from datetime import timedelta
from core.database import get_connection, upsert_dataframe
from core.queries import update_job_status, get_job_state
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.octopus.energy/v1"

def get_auth():
    api_key = os.getenv("OCTOPUS_API_KEY")
    if not api_key:
        raise ValueError("API Key is missing. Check your .env file.")
    return (api_key, '')

def _fetch_paginated_chunk(url, period_from, period_to):
    rt = pd.to_datetime(period_to, utc=True).strftime('%Y-%m-%dT%H:%M:%SZ')
    rf = pd.to_datetime(period_from, utc=True).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    params = {'period_from': rf, 'period_to': rt, 'page_size': 25000}
    results = []
    next_url = url
    
    while next_url:
        resp_params = params if next_url == url else None
        response = requests.get(next_url, auth=get_auth(), params=resp_params)
        
        if response.status_code != 200:
            print(f"API Error {response.status_code}: {response.text}")
            raise Exception(f"Failed to fetch: HTTP {response.status_code}")
            
        data = response.json()
        results.extend(data.get('results', []))
        next_url = data.get('next')
        
    return results

def _chunked_fetch(endpoint_name, fetch_url, start_date, end_date, formatter_func, db_table, conflict_cols):
    update_job_status(endpoint_name, 'RUNNING')
    try:
        current_start = pd.to_datetime(start_date, utc=True)
        final_end = pd.to_datetime(end_date, utc=True)
        
        if current_start > final_end:
            current_start, final_end = final_end, current_start
            
        while current_start < final_end:
            chunk_end = min(current_start + timedelta(days=7), final_end)
            
            print(f"[{endpoint_name}] Syncing {current_start.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}...")
            results = _fetch_paginated_chunk(fetch_url, current_start, chunk_end)
            
            if results:
                df = formatter_func(results)
                with get_connection() as conn:
                    upsert_dataframe(conn, df, db_table, conflict_cols)
                    
                max_ts = df['interval_start'].max()
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
        print(f"✅ [{endpoint_name}] Catch-up Process Complete.")
    
    except Exception as e:
        update_job_status(endpoint_name, f'ERROR: {str(e)}')
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
    try:
        prod_resp = requests.get(f"{BASE_URL}/products/{product_code}/")
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
            print(f"✅ [{product_code}] Core Product Catalog Saved")
    except Exception as e:
        update_job_status(f'product_{product_code}', f'ERROR: {str(e)}')
        
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
    account_number = os.getenv("OCTOPUS_ACCOUNT_NUMBER")
    if not account_number:
        print("⚠️ No OCTOPUS_ACCOUNT_NUMBER found in .env. Skipping account fetch.")
        return

    update_job_status('accounts', 'RUNNING')
    try:
        print("[accounts] Synchronizing Account Details...")
        url = f"{BASE_URL}/accounts/{account_number}/"
        response = requests.get(url, auth=get_auth())
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch accounts")
            
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

        update_job_status('accounts', 'SUCCESS')
        print(f"✅ [accounts] Sync Complete")
    except Exception as e:
        update_job_status('accounts', f'ERROR: {str(e)}')
        print(f"❌ [accounts] Sync Failed: {e}")
