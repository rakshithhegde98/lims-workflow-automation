"""
Database module for LIMS Workflow Automation Tool.

This module handles all SQLite database operations including:
- Creating the samples table
- Loading CSV data into the database
- Running SQL queries for reporting and delay detection

In a real LabVantage LIMS, these tables would be part of the LIMS schema
(e.g., s_sample, s_sample_test). Here we simulate a simplified version.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent / "lims_samples.db"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Create and return a database connection."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Create the samples table in SQLite.

    This mirrors a simplified version of the LabVantage s_sample table
    with key fields for tracking sample lifecycle.
    """
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
    """
    Load sample data from a CSV file into the SQLite database.

    Args:
        csv_path: Path to the CSV file
        conn: SQLite connection

    Returns:
        Number of records loaded
    """
    df = pd.read_csv(csv_path)

    # Validate required columns
    required_cols = ['sample_id', 'request_id', 'test_type', 'status',
                     'created_date', 'updated_date']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    # Add optional columns with defaults if missing
    if 'priority' not in df.columns:
        df['priority'] = 'NORMAL'
    if 'department' not in df.columns:
        df['department'] = 'General'

    # Initialize delay columns
    df['is_delayed'] = 0
    df['delay_days'] = 0.0

    # Drop existing data and reload
    cursor = conn.cursor()
    cursor.execute("DELETE FROM samples")
    conn.commit()

    # Insert records
    df.to_sql('samples', conn, if_exists='replace', index=False)

    return len(df)


def run_delay_detection(conn: sqlite3.Connection, threshold_days: int = 3,
                        reference_date: str = None) -> int:
    """
    Detect delayed samples using SQL.

    A sample is considered DELAYED if:
    - Its status is NOT 'COMPLETED'
    - It has been in the system for more than `threshold_days` days

    This is the kind of query a LabVantage admin would run regularly
    to identify bottlenecks in the lab workflow.

    Args:
        conn: SQLite connection
        threshold_days: Number of days after which a sample is considered delayed
        reference_date: Date to calculate delay from (defaults to today)

    Returns:
        Number of delayed samples found
    """
    if reference_date is None:
        reference_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor = conn.cursor()

    # SQL query to detect delays — this demonstrates real SQL skills
    # julianday() is SQLite's date function, similar to DATEDIFF in other DBs
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

    # Count delayed samples
    count_query = "SELECT COUNT(*) as cnt FROM samples WHERE is_delayed = 1"
    result = cursor.execute(count_query).fetchone()
    return result['cnt'] if result else 0


def get_summary_stats(conn: sqlite3.Connection) -> dict:
    """
    Generate summary statistics using SQL aggregation.

    Returns a dictionary with counts by status and delay information.
    """
    cursor = conn.cursor()

    # Overall counts by status
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

    # Delayed samples by priority
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

    # Delayed samples by department
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

    # Delayed samples by test type
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

    # Average delay days
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
    """
    Retrieve all delayed samples with details, ordered by delay severity.

    This query demonstrates JOIN-like thinking and ordering by business priority.
    """
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
    """Retrieve all samples from the database."""
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
    """
    Get lifecycle details for a specific sample.

    In LabVantage, this would involve querying s_sample and related
    audit trail tables to track status changes.
    """
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
