import sqlite3
import os

DB_NAME = "setrum.db"

def get_connection():
    """Returns a connection to the local SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def upsert_dataframe(conn, df, table_name, conflict_cols):
    """
    Safely UPSERTs a pandas DataFrame into a SQLite table.
    This guarantees idempotency (no duplicate entries on chunk re-runs).
    """
    if df.empty:
        return

    records = df.to_dict(orient='records')
    columns = list(records[0].keys())
    
    placeholders = ", ".join(["?"] * len(columns))
    columns_str = ", ".join(columns)
    
    update_cols = [col for col in columns if col not in conflict_cols]
    if update_cols:
        updates_str = ", ".join([f"{c}=excluded.{c}" for c in update_cols])
        conflict_action = f"DO UPDATE SET {updates_str}"
    else:
        conflict_action = "DO NOTHING"
        
    query = f'''
        INSERT INTO {table_name} ({columns_str})
        VALUES ({placeholders})
        ON CONFLICT({", ".join(conflict_cols)})
        {conflict_action}
    '''
    
    values = [[record[c] for c in columns] for record in records]
    
    with conn:
        cursor = conn.cursor()
        cursor.executemany(query, values)


def init_db():
    """Initializes the database schemas safely."""
    print(f"Initializing Local Database: {DB_NAME}")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Consumptions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_consumptions (
                interval_start TEXT,
                mpan TEXT,
                meter_serial_number TEXT,
                interval_end TEXT,
                consumption_kwh REAL,
                PRIMARY KEY (interval_start, mpan, meter_serial_number)
            )
        ''')
        
        # 2a. Electricity Standard Unit Rates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_electricity_standard_unit_rates (
                interval_start TEXT,
                tariff_code TEXT,
                interval_end TEXT,
                value_inc_vat REAL,
                value_exc_vat REAL,
                PRIMARY KEY (interval_start, tariff_code)
            )
        ''')
        
        # 2b. Electricity Standing Charges
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_electricity_standing_charges (
                interval_start TEXT,
                tariff_code TEXT,
                interval_end TEXT,
                value_inc_vat REAL,
                value_exc_vat REAL,
                PRIMARY KEY (interval_start, tariff_code)
            )
        ''')
        
        # 3. Accounts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_accounts (
                account_number TEXT,
                account_id INTEGER,
                moved_in_at TEXT,
                moved_out_at TEXT,
                address_line_1 TEXT,
                address_line_2 TEXT,
                address_line_3 TEXT,
                town TEXT,
                county TEXT,
                postcode TEXT,
                PRIMARY KEY (account_number, account_id)
            )
        ''')

        # 3a. Electricity Meters
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_electricity_meters (
                account_number TEXT,
                account_id INTEGER,
                mpan TEXT,
                serial_number TEXT,
                PRIMARY KEY (account_number, account_id, mpan, serial_number)
            )
        ''')

        # 3b. Electricity Agreements
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_electricity_agreements (
                account_number TEXT,
                account_id INTEGER,
                mpan TEXT,
                tariff_code TEXT,
                valid_from TEXT,
                valid_to TEXT,
                PRIMARY KEY (account_number, account_id, mpan, tariff_code, valid_from)
            )
        ''')
        
        # 4. Products
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_products (
                product_code TEXT PRIMARY KEY,
                full_name TEXT,
                description TEXT,
                brand TEXT
            )
        ''')
        
        # 5. Job Runs (Track background task state)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_runs (
                endpoint_name TEXT PRIMARY KEY,
                status TEXT,
                last_successful_timestamp TEXT,
                oldest_successful_timestamp TEXT,
                last_run_at TEXT,
                error_message TEXT
            )
        ''')

        # 6. Annotations: free-text + time range, account-scoped
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                period_start_utc TEXT NOT NULL,
                period_end_utc TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'half-hourly',
                comment TEXT,
                position_x INTEGER,
                position_y INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        # Migration for pre-source DBs: add the column if missing, then
        # smart-backfill — annotations covering ≥1 day starting at midnight
        # are 'daily'; everything else is 'half-hourly'.
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(annotations)").fetchall()}
        if "source" not in existing_cols:
            cursor.execute(
                "ALTER TABLE annotations ADD COLUMN source TEXT NOT NULL DEFAULT 'half-hourly'"
            )
            cursor.execute("""
                UPDATE annotations
                SET source = CASE
                    WHEN (julianday(period_end_utc) - julianday(period_start_utc)) >= 1.0
                         AND time(period_start_utc) = '00:00:00'
                    THEN 'daily'
                    ELSE 'half-hourly'
                END
            """)

        # Position columns for the Annotations canvas. NULL = "no manual
        # position yet" — the UI lays the note out on a default grid.
        if "position_x" not in existing_cols:
            cursor.execute("ALTER TABLE annotations ADD COLUMN position_x INTEGER")
        if "position_y" not in existing_cols:
            cursor.execute("ALTER TABLE annotations ADD COLUMN position_y INTEGER")

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_period_start ON annotations(period_start_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_period_end ON annotations(period_end_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_account_period ON annotations(account_id, period_start_utc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotations_source ON annotations(source)')

        # 7. Tags: case-insensitive unique name, optional color for chart-band styling
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                color TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        # 8. Annotation <-> Tag junction (many-to-many)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annotation_tags (
                annotation_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (annotation_id, tag_id),
                FOREIGN KEY (annotation_id) REFERENCES annotations(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_annotation_tags_tag ON annotation_tags(tag_id, annotation_id)')

        # Keep updated_at honest on annotation edits
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS trg_annotations_updated_at
            AFTER UPDATE ON annotations
            FOR EACH ROW
            BEGIN
                UPDATE annotations SET updated_at = datetime('now') WHERE id = OLD.id;
            END
        ''')

        conn.commit()
    print("Schema Initialization Complete.")

if __name__ == "__main__":
    init_db()
