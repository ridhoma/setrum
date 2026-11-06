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

        _safe_progress(progress_cb, "accounts", 1, 4)
        fetch_accounts()

        active_meters = get_active_meters()
        active_tariffs = get_active_tariffs()

        total_fetches = len(active_meters) + len(active_tariffs)
        total_steps = max(2 + total_fetches, 3)
        completed_steps = 1
        _safe_progress(progress_cb, "meters & tariffs", completed_steps, total_steps)

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

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ Sub-thread execution failed: {e}")
                completed_steps += 1
                _safe_progress(progress_cb, "meters & tariffs", completed_steps, total_steps)

            _safe_progress(progress_cb, "analytics tables", total_steps - 1, total_steps)
            transform_analytics()
            _safe_progress(progress_cb, "complete", total_steps, total_steps)

        update_job_status(SYNC_JOB_NAME, 'COMPLETE')
        print("✅ Sync complete.")
    except Exception as e:
        update_job_status(SYNC_JOB_NAME, 'ERROR', error_message=str(e))
        print(f"❌ Sync failed: {e}")
        raise

def chunked_backfill(
    account_id: int,
    start_date: str,
    end_date: str,
    chunk_days: int = 14,
    progress_cb: Optional[ProgressCb] = None,
):
    """Backfills consumption and tariff history in discrete, manageable chunks.

    Divides [start_date, end_date] into windows of `chunk_days` days.
    For each chunk:
      1. Fetches consumption for all meters of the account.
      2. Fetches tariff rates for all agreements of the account.
      3. Immediately triggers transform_analytics() so data is committed & available in the mart.
      4. Invokes progress_cb(step_label, completed_chunks, total_chunks).
    """
    import pandas as pd
    selected_meters = get_meters_by_account(account_id)
    selected_tariffs = get_tariffs_by_account(account_id)

    dt_start = pd.to_datetime(start_date, utc=True)
    dt_end = pd.to_datetime(end_date, utc=True)
    if dt_start > dt_end:
        dt_start, dt_end = dt_end, dt_start

    # Build windows
    windows = []
    curr = dt_start
    while curr < dt_end:
        nxt = min(curr + timedelta(days=chunk_days), dt_end)
        windows.append((curr.strftime("%Y-%m-%dT%H:%M:%SZ"), nxt.strftime("%Y-%m-%dT%H:%M:%SZ")))
        curr = nxt

    total_chunks = len(windows)
    if total_chunks == 0:
        return

    print(f"🚀 Formulating Chunked Backfill ({total_chunks} chunks of ~{chunk_days}d) for account {account_id}...")
    _safe_progress(progress_cb, "Starting backfill...", 0, total_chunks)

    for idx, (w_start, w_end) in enumerate(windows, 1):
        step_label = f"Chunk {idx}/{total_chunks}: {w_start[:10]} → {w_end[:10]}"
        print(f"📦 [{step_label}] Fetching data...")

        futures = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            for mpan, serial in selected_meters:
                futures.append(executor.submit(fetch_consumptions, w_start, w_end, mpan, serial))

            for tariff in selected_tariffs:
                futures.append(executor.submit(fetch_tariff_pricing, w_start, w_end, tariff))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ Backfill sub-task failed for {w_start}..{w_end}: {e}")

        # Materialize analytics after each chunk so newly fetched data lands immediately
        transform_analytics()
        _safe_progress(progress_cb, step_label, idx, total_chunks)

    print(f"✅ Chunked Backfill complete for account {account_id}.")


def manual_backfill(account_id, start_date, end_date):
    """Explicit UI-triggered backward history block sync for a selected property."""
    return chunked_backfill(account_id, start_date, end_date, chunk_days=14)

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
