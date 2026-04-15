"""
SQLite operations for sample tracking.

Handles table creation, CSV ingestion, delay detection,
and all the reporting queries.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent / "lims_samples.db"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Open a connection. Defaults to the on-disk DB if no path given."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Set up the samples table (simplified version of LabVantage s_sample)."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            sample_id       TEXT PRIMARY KEY,
            request_id      TEXT NOT NULL,
            test_type       TEXT NOT NULL,
            status          TEXT NOT NULL CHECK(status IN ('RECEIVED', 'IN_PROGRESS', 'COMPLETED')),
            priority        TEXT DEFAULT 'NORMAL' CHECK(priority IN ('NORMAL', 'HIGH', 'URGENT')),
            department      TEXT,
            created_date    TIMESTAMP NOT NULL,
            updated_date    TIMESTAMP NOT NULL,
            is_delayed      INTEGER DEFAULT 0,
            delay_days      REAL DEFAULT 0
        )
    """)
    conn.commit()


def load_csv_to_db(csv_path: str, conn: sqlite3.Connection) -> int:
    """Read a CSV into the samples table. Returns row count."""
    df = pd.read_csv(csv_path)

    required_cols = ['sample_id', 'request_id', 'test_type', 'status',
                     'created_date', 'updated_date']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Fill in optional columns if they're not in the CSV
    if 'priority' not in df.columns:
        df['priority'] = 'NORMAL'
    if 'department' not in df.columns:
        df['department'] = 'General'

    df['is_delayed'] = 0
    df['delay_days'] = 0.0

    cursor = conn.cursor()
    cursor.execute("DELETE FROM samples")
    conn.commit()

    df.to_sql('samples', conn, if_exists='replace', index=False)

    return len(df)


def run_delay_detection(conn: sqlite3.Connection, threshold_days: int = 3,
                        reference_date: str = None) -> int:
    """
    Flag samples as delayed if they're not COMPLETED and have been
    sitting longer than threshold_days. Returns count of delayed samples.
    """
    if reference_date is None:
        reference_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor = conn.cursor()

    # julianday() is SQLite's way of doing date math — similar to DATEDIFF elsewhere
    update_query = """
        UPDATE samples
        SET
            is_delayed = CASE
                WHEN status != 'COMPLETED'
                     AND julianday(?) - julianday(created_date) > ?
                THEN 1
                ELSE 0
            END,
            delay_days = CASE
                WHEN status != 'COMPLETED'
                     AND julianday(?) - julianday(created_date) > ?
                THEN ROUND(julianday(?) - julianday(created_date), 1)
                ELSE 0
            END
    """
    cursor.execute(update_query, (
        reference_date, threshold_days,
        reference_date, threshold_days,
        reference_date
    ))
    conn.commit()

    count_query = "SELECT COUNT(*) as cnt FROM samples WHERE is_delayed = 1"
    result = cursor.execute(count_query).fetchone()
    return result['cnt'] if result else 0


def get_summary_stats(conn: sqlite3.Connection) -> dict:
    """Pull aggregate stats — status counts, delay breakdowns, averages."""
    cursor = conn.cursor()

    status_query = """
        SELECT
            COUNT(*) as total_samples,
            SUM(CASE WHEN status = 'RECEIVED' THEN 1 ELSE 0 END) as received_count,
            SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress_count,
            SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_count,
            SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) as delayed_count
        FROM samples
    """
    row = cursor.execute(status_query).fetchone()

    stats = {
        'total_samples': row['total_samples'],
        'received': row['received_count'],
        'in_progress': row['in_progress_count'],
        'completed': row['completed_count'],
        'delayed': row['delayed_count'],
    }

    # Ordered by business priority so URGENT shows up first
    priority_query = """
        SELECT priority, COUNT(*) as cnt
        FROM samples
        WHERE is_delayed = 1
        GROUP BY priority
        ORDER BY
            CASE priority
                WHEN 'URGENT' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'NORMAL' THEN 3
            END
    """
    stats['delayed_by_priority'] = {
        r['priority']: r['cnt']
        for r in cursor.execute(priority_query).fetchall()
    }

    dept_query = """
        SELECT department, COUNT(*) as cnt
        FROM samples
        WHERE is_delayed = 1
        GROUP BY department
        ORDER BY cnt DESC
    """
    stats['delayed_by_department'] = {
        r['department']: r['cnt']
        for r in cursor.execute(dept_query).fetchall()
    }

    test_query = """
        SELECT test_type, COUNT(*) as cnt
        FROM samples
        WHERE is_delayed = 1
        GROUP BY test_type
        ORDER BY cnt DESC
    """
    stats['delayed_by_test_type'] = {
        r['test_type']: r['cnt']
        for r in cursor.execute(test_query).fetchall()
    }

    avg_query = """
        SELECT
            ROUND(AVG(delay_days), 1) as avg_delay,
            ROUND(MAX(delay_days), 1) as max_delay
        FROM samples
        WHERE is_delayed = 1
    """
    avg_row = cursor.execute(avg_query).fetchone()
    stats['avg_delay_days'] = avg_row['avg_delay'] or 0
    stats['max_delay_days'] = avg_row['max_delay'] or 0

    return stats


def get_delayed_samples(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get all delayed samples, sorted by priority then worst delay first."""
    query = """
        SELECT
            sample_id,
            request_id,
            test_type,
            status,
            priority,
            department,
            created_date,
            updated_date,
            delay_days
        FROM samples
        WHERE is_delayed = 1
        ORDER BY
            CASE priority
                WHEN 'URGENT' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'NORMAL' THEN 3
            END,
            delay_days DESC
    """
    return pd.read_sql_query(query, conn)


def get_all_samples(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch every sample, ordered by creation date."""
    query = """
        SELECT
            sample_id,
            request_id,
            test_type,
            status,
            priority,
            department,
            created_date,
            updated_date,
            is_delayed,
            delay_days
        FROM samples
        ORDER BY created_date
    """
    return pd.read_sql_query(query, conn)


def get_sample_lifecycle(conn: sqlite3.Connection, sample_id: str) -> dict:
    """Look up a single sample's full record."""
    cursor = conn.cursor()
    query = """
        SELECT *
        FROM samples
        WHERE sample_id = ?
    """
    row = cursor.execute(query, (sample_id,)).fetchone()
    if row:
        return dict(row)
    return None
