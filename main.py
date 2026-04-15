"""
CLI entry point — loads sample data, runs delay detection, prints a report.

Usage:
    python main.py
    python main.py --csv path/to/data.csv --threshold 5
    python main.py --save-report --ai-summary
"""

import argparse
import sys
from pathlib import Path

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
        help='Days before a sample is considered delayed (default: 3)'
    )
    parser.add_argument(
        '--save-report',
        action='store_true',
        help='Save the report to a file'
    )
    parser.add_argument(
        '--ai-summary',
        action='store_true',
        help='Use OpenAI for the summary (requires OPENAI_API_KEY)'
    )

    args = parser.parse_args()

    print("\n🔬 LIMS Workflow Automation Tool")
    print("=" * 40)

    # Set up in-memory DB
    print("\n📦 Step 1: Setting up database...")
    conn = get_connection(":memory:")
    create_tables(conn)
    print("   ✅ Database ready")

    # Load CSV
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

    # Run delay detection
    print(f"\n🔍 Step 3: Detecting delays (threshold: {args.threshold} days)...")
    delayed_count = run_delay_detection(conn, threshold_days=args.threshold)
    print(f"   ⚠️  Found {delayed_count} delayed sample(s)")

    # Pull stats
    print("\n📊 Step 4: Generating statistics...")
    stats = get_summary_stats(conn)
    delayed_df = get_delayed_samples(conn)

    # Print report
    print("\n📝 Step 5: Generating report...\n")
    report = generate_daily_summary(stats, delayed_df, args.threshold)
    print(report)

    # Save if requested
    if args.save_report:
        report_path = save_report_to_file(report)
        print(f"\n💾 Report saved to: {report_path}")

        if not delayed_df.empty:
            csv_path = export_delayed_to_csv(delayed_df)
            print(f"💾 Delayed samples CSV saved to: {csv_path}")

    # Summary
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
