import pandas as pd
from core.database import get_connection

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
