from datetime import datetime, timezone
import threading
import time
import pandas as pd
from core.database import get_connection

PROCESS_LOG_RETENTION_LIMIT = 100

_run_context_lock = threading.Lock()
_active_run_context = {
    "run_id": None,
    "trigger_source": "System",
}


def set_run_context(run_id=None, trigger_source="System"):
    with _run_context_lock:
        _active_run_context["run_id"] = run_id
        _active_run_context["trigger_source"] = trigger_source or "System"


def get_run_context():
    with _run_context_lock:
        return _active_run_context["run_id"], _active_run_context["trigger_source"]


def _ensure_process_logs_table(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS process_run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            trigger_source TEXT DEFAULT 'System',
            process_type TEXT NOT NULL,
            endpoint_name TEXT NOT NULL,
            target_table TEXT,
            status TEXT NOT NULL,
            rows_affected INTEGER DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_ms INTEGER,
            details TEXT
        )
    ''')


def start_process_log(
    process_type,
    endpoint_name,
    target_table=None,
    details=None,
    run_id=None,
    trigger_source=None,
):
    """Record the start of a backend process run and return (log_id, perf_counter_t0)."""
    t0 = time.perf_counter()
    ctx_run_id, ctx_trigger = get_run_context()
    eff_run_id = run_id if run_id is not None else ctx_run_id
    eff_trigger = trigger_source if trigger_source is not None else ctx_trigger
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            _ensure_process_logs_table(cursor)
            cursor.execute(
                """
                INSERT INTO process_run_logs (
                    run_id, trigger_source, process_type, endpoint_name,
                    target_table, status, rows_affected, started_at, details
                ) VALUES (?, ?, ?, ?, ?, 'RUNNING', 0, ?, ?)
                """,
                (eff_run_id, eff_trigger, process_type, endpoint_name, target_table, now_str, details),
            )
            log_id = cursor.lastrowid
            cursor.execute(
                """
                DELETE FROM process_run_logs
                WHERE id NOT IN (
                    SELECT id FROM process_run_logs
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (PROCESS_LOG_RETENTION_LIMIT,),
            )
            conn.commit()
            return log_id, t0
    except Exception as e:
        print(f"⚠️ Failed to start_process_log for {endpoint_name}: {e}")
        return None, t0


def finish_process_log(
    log_id,
    t0,
    status="SUCCESS",
    rows_affected=0,
    details=None,
):
    """Complete a backend process run log entry and enforce 100-run retention."""
    if log_id is None:
        return
    duration_ms = max(0, int((time.perf_counter() - t0) * 1000))
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if details is not None:
                cursor.execute(
                    """
                    UPDATE process_run_logs
                    SET status = ?,
                        rows_affected = ?,
                        finished_at = ?,
                        duration_ms = ?,
                        details = ?
                    WHERE id = ?
                    """,
                    (status, int(rows_affected or 0), now_str, duration_ms, details, log_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE process_run_logs
                    SET status = ?,
                        rows_affected = ?,
                        finished_at = ?,
                        duration_ms = ?
                    WHERE id = ?
                    """,
                    (status, int(rows_affected or 0), now_str, duration_ms, log_id),
                )
            cursor.execute(
                """
                DELETE FROM process_run_logs
                WHERE id NOT IN (
                    SELECT id FROM process_run_logs
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (PROCESS_LOG_RETENTION_LIMIT,),
            )
            conn.commit()
    except Exception as e:
        print(f"⚠️ Failed to finish_process_log for id={log_id}: {e}")

def update_job_status(endpoint_name, status, last_success=None, oldest_success=None, error_message=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO job_runs (endpoint_name, status)
            VALUES (?, ?)
        """, (endpoint_name, status))
        
        updates = ["status = ?", "last_run_at = CURRENT_TIMESTAMP", "error_message = ?"]
        params = [status, error_message]
        
        if last_success is not None:
            updates.append("last_successful_timestamp = ?")
            params.append(last_success)
        if oldest_success is not None:
            updates.append("oldest_successful_timestamp = ?")
            params.append(oldest_success)
            
        params.append(endpoint_name)
        
        query = f"""
            UPDATE job_runs 
            SET {', '.join(updates)}
            WHERE endpoint_name = ?
        """
        cursor.execute(query, params)
        conn.commit()

def get_job_state(endpoint_name):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_runs WHERE endpoint_name = ?", (endpoint_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {'last_successful_timestamp': None, 'oldest_successful_timestamp': None, 'status': 'NOT_STARTED'}

def get_meters_by_account(account_id):
    with get_connection() as conn:
        query = "SELECT mpan, serial_number FROM source_electricity_meters WHERE account_id = ?"
        try:
            df = pd.read_sql_query(query, conn, params=(account_id,))
            return df.to_records(index=False).tolist()
        except Exception:
            return []

def get_active_meters():
    with get_connection() as conn:
        query = """
            SELECT em.mpan, em.serial_number 
            FROM source_electricity_meters em
            JOIN source_accounts a ON em.account_number = a.account_number AND em.account_id = a.account_id
            WHERE a.moved_out_at IS NULL
        """
        try:
            df = pd.read_sql_query(query, conn)
            return df.to_records(index=False).tolist()
        except Exception:
            return []

def get_tariffs_by_account(account_id):
    with get_connection() as conn:
        query = "SELECT DISTINCT tariff_code FROM source_electricity_agreements WHERE account_id = ?"
        try:
            df = pd.read_sql_query(query, conn, params=(account_id,))
            return df['tariff_code'].tolist()
        except Exception:
            return []

def get_active_tariffs():
    with get_connection() as conn:
        query = """
            SELECT DISTINCT tariff_code 
            FROM source_electricity_agreements
            WHERE valid_to IS NULL OR valid_to > datetime('now')
        """
        try:
            df = pd.read_sql_query(query, conn)
            return df['tariff_code'].tolist()
        except Exception:
            return []
