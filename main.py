"""
LIMS Workflow Automation Tool — Main Entry Point (CLI)

This script demonstrates the complete workflow:
1. Load sample data from CSV into SQLite
2. Run delay detection using SQL queries
3. Generate summary statistics
4. Produce a formatted report
5. Generate an AI/rule-based summary

Usage:
    python main.py                          # Use default sample data
    python main.py --csv path/to/data.csv   # Use custom CSV file
    python main.py --threshold 5            # Set delay threshold to 5 days
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from db.database import (
    get_connection,
    create_tables,
    load_csv_to_db,
    run_delay_detection,
    get_summary_stats,
    get_delayed_samples,
    get_all_samples,
)
from core.report_generator import (
    generate_daily_summary,
    save_report_to_file,
    export_delayed_to_csv,
)
from core.ai_summary import generate_rule_based_summary, generate_openai_summary


def main():
    parser = argparse.ArgumentParser(
        description="LIMS Workflow Automation Tool — Sample Delay Detection & Reporting"
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=str(Path(__file__).parent / 'data' / 'sample_data.csv'),
        help='Path to the CSV file with sample data'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=3,
        help='Number of days after which a sample is considered delayed (default: 3)'
    )
    parser.add_argument(
        '--save-report',
        action='store_true',
        help='Save the report to a file'
    )
    parser.add_argument(
        '--ai-summary',
        action='store_true',
        help='Generate AI-powered summary (requires OpenAI API key)'
    )

    args = parser.parse_args()

    print("\n🔬 LIMS Workflow Automation Tool")
    print("=" * 40)

    # Step 1: Connect to database
    print("\n📦 Step 1: Setting up database...")
    conn = get_connection(":memory:")  # Use in-memory DB for CLI
    create_tables(conn)
    print("   ✅ Database ready")

    # Step 2: Load CSV data
    print(f"\n📂 Step 2: Loading data from {args.csv}...")
    try:
        record_count = load_csv_to_db(args.csv, conn)
        print(f"   ✅ Loaded {record_count} samples")
    except FileNotFoundError:
        print(f"   ❌ File not found: {args.csv}")
        sys.exit(1)
    except ValueError as e:
        print(f"   ❌ Data error: {e}")
        sys.exit(1)

    # Step 3: Run delay detection
    print(f"\n🔍 Step 3: Detecting delays (threshold: {args.threshold} days)...")
    delayed_count = run_delay_detection(conn, threshold_days=args.threshold)
    print(f"   ⚠️  Found {delayed_count} delayed sample(s)")

    # Step 4: Get statistics
    print("\n📊 Step 4: Generating statistics...")
    stats = get_summary_stats(conn)
    delayed_df = get_delayed_samples(conn)

    # Step 5: Generate report
    print("\n📝 Step 5: Generating report...\n")
    report = generate_daily_summary(stats, delayed_df, args.threshold)
    print(report)

    # Step 6: Save report if requested
    if args.save_report:
        report_path = save_report_to_file(report)
        print(f"\n💾 Report saved to: {report_path}")

        if not delayed_df.empty:
            csv_path = export_delayed_to_csv(delayed_df)
            print(f"💾 Delayed samples CSV saved to: {csv_path}")

    # Step 7: AI Summary
    print("\n" + "=" * 70)
    if args.ai_summary:
        print("\n🤖 Generating AI Summary...")
        summary = generate_openai_summary(stats, delayed_df)
    else:
        print("\n💡 Generating Smart Summary...")
        summary = generate_rule_based_summary(stats, delayed_df)

    print(summary)
    print()

    conn.close()


if __name__ == "__main__":
    main()
