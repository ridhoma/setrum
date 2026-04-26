from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from core.queries import get_active_meters, get_active_tariffs, get_job_state, get_meters_by_account, get_tariffs_by_account, update_job_status
from core.fetchers import fetch_accounts, fetch_consumptions, fetch_tariff_pricing

SYNC_JOB_NAME = '_sync'

ProgressCb = Callable[[str, int, int], None]


def _safe_progress(cb: Optional[ProgressCb], step: str, current: int, total: int) -> None:
    if cb is None:
        return
    try:
        cb(step, current, total)
    except Exception as e:
        # Never let a UI-side progress hook crash the sync.
        print(f"⚠️ progress_cb raised: {e}")


def auto_catch_up(progress_cb: Optional[ProgressCb] = None):
    """Automatically forwards-fills missing data from the last known state up to NOW.

    `progress_cb(step, current, total)` is called after the accounts refresh,
    after each fetch future completes, and around the analytics transform.
    """
    try:
        update_job_status(SYNC_JOB_NAME, 'RUNNING')
        now = datetime.now(timezone.utc).isoformat()

        _safe_progress(progress_cb, "accounts", 0, 1)
        fetch_accounts()
        _safe_progress(progress_cb, "accounts", 1, 1)

        active_meters = get_active_meters()
        active_tariffs = get_active_tariffs()

        total_fetches = len(active_meters) + len(active_tariffs)
        _safe_progress(progress_cb, "fetch", 0, total_fetches)

        print("🚀 Formulating Async Pipeline for all delta data synchronization...")

        futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            if not active_meters:
                print("⚠️ No active meters found in DB to sync consumptions.")
            for mpan, serial in active_meters:
                job_name = f'consumptions_{mpan}_{serial}'
                c_state = get_job_state(job_name)
                c_start = c_state.get('last_successful_timestamp') or (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                futures.append(executor.submit(fetch_consumptions, c_start, now, mpan, serial))

            for tariff in active_tariffs:
                p_state = get_job_state(f'unit_rates_{tariff}')
                p_start = p_state.get('last_successful_timestamp') or (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
                futures.append(executor.submit(fetch_tariff_pricing, p_start, now, tariff))

            done = 0
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ Sub-thread execution failed: {e}")
                done += 1
                _safe_progress(progress_cb, "fetch", done, total_fetches)

            _safe_progress(progress_cb, "transform", 0, 1)
            transform_analytics()
            _safe_progress(progress_cb, "transform", 1, 1)

        update_job_status(SYNC_JOB_NAME, 'COMPLETE')
        print("✅ Sync complete.")
    except Exception as e:
        update_job_status(SYNC_JOB_NAME, 'ERROR', error_message=str(e))
        print(f"❌ Sync failed: {e}")
        raise

def manual_backfill(account_id, start_date, end_date):
    """Explicit UI-triggered backward history block sync for a selected property."""
    selected_meters = get_meters_by_account(account_id)
    selected_tariffs = get_tariffs_by_account(account_id)
    
    print(f"🚀 Formulating Async Pipeline for manual backfill of account {account_id}...")
    
    futures = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        if not selected_meters:
            print(f"⚠️ No meters found for account_id {account_id}")
            
        for mpan, serial in selected_meters:
            futures.append(executor.submit(fetch_consumptions, start_date, end_date, mpan, serial))
            
        for tariff in selected_tariffs:
            futures.append(executor.submit(fetch_tariff_pricing, start_date, end_date, tariff))
            
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Sub-thread execution failed: {e}")

        # Post-Processing: ELT Transformation
        transform_analytics()

def transform_analytics():
    """Drops and rebuilds materialized native SQL presentation tables for Streamlit."""
    print("⚙️ Materializing Analytics Data Marts (ELT)...")
    from core.database import get_connection
    from core.transformations import MODELS
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN")
        
        for model in MODELS:
            table_name = model["table_name"]
            query = model["query"]
            
            print(f"   Building {table_name}...")
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            cursor.execute(f"CREATE TABLE {table_name} AS {query}")
        
        cursor.execute("COMMIT")
        print("✅ Analytics Transformation Complete.")
