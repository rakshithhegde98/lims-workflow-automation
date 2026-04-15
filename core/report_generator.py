"""
Report formatting and file export.

Builds the daily summary text report and handles saving
reports / delayed-sample CSVs to disk.
"""

import pandas as pd
from datetime import datetime
from pathlib import Path


def generate_daily_summary(stats: dict, delayed_df: pd.DataFrame,
                           threshold_days: int = 3) -> str:
    """Build a formatted text report from stats and delayed sample data."""
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    lines = []
    lines.append("=" * 70)
    lines.append("       LIMS DAILY SAMPLE STATUS REPORT")
    lines.append(f"       Generated: {report_date}")
    lines.append(f"       Delay Threshold: {threshold_days} days")
    lines.append("=" * 70)
    lines.append("")

    # --- Overall Summary ---
    lines.append("📊 OVERALL SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Total Samples      : {stats['total_samples']}")
    lines.append(f"  ✅ Completed        : {stats['completed']}")
    lines.append(f"  🔄 In Progress      : {stats['in_progress']}")
    lines.append(f"  📥 Received         : {stats['received']}")
    lines.append(f"  ⚠️  Delayed          : {stats['delayed']}")
    lines.append("")

    if stats['total_samples'] > 0:
        completion_rate = (stats['completed'] / stats['total_samples']) * 100
        lines.append(f"  Completion Rate    : {completion_rate:.1f}%")
    lines.append("")

    # --- Delay breakdown ---
    if stats['delayed'] > 0:
        lines.append("⚠️  DELAY ANALYSIS")
        lines.append("-" * 40)
        lines.append(f"  Average Delay      : {stats['avg_delay_days']} days")
        lines.append(f"  Maximum Delay      : {stats['max_delay_days']} days")
        lines.append("")

        if stats.get('delayed_by_priority'):
            lines.append("  Delayed by Priority:")
            for priority, count in stats['delayed_by_priority'].items():
                icon = "🔴" if priority == "URGENT" else "🟡" if priority == "HIGH" else "🟢"
                lines.append(f"    {icon} {priority:10s} : {count}")
            lines.append("")

        if stats.get('delayed_by_department'):
            lines.append("  Delayed by Department:")
            for dept, count in stats['delayed_by_department'].items():
                lines.append(f"    📁 {dept:20s} : {count}")
            lines.append("")

        if stats.get('delayed_by_test_type'):
            lines.append("  Delayed by Test Type:")
            for test, count in stats['delayed_by_test_type'].items():
                lines.append(f"    🧪 {test:20s} : {count}")
            lines.append("")

        # Individual delayed samples
        lines.append("📋 DELAYED SAMPLES DETAIL")
        lines.append("-" * 70)
        lines.append(f"  {'Sample ID':<12} {'Test Type':<22} {'Status':<14} "
                     f"{'Priority':<10} {'Days':<6}")
        lines.append("  " + "-" * 64)

        for _, row in delayed_df.iterrows():
            lines.append(
                f"  {row['sample_id']:<12} {row['test_type']:<22} "
                f"{row['status']:<14} {row['priority']:<10} "
                f"{row['delay_days']:<6}"
            )
        lines.append("")
    else:
        lines.append("✅ No delayed samples found! All samples are on track.")
        lines.append("")

    lines.append("=" * 70)
    lines.append("       END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def save_report_to_file(report_text: str, output_dir: str = None) -> str:
    """Write the report to a timestamped .txt file. Returns the file path."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "reports"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"lims_report_{timestamp}.txt"
    filepath = output_path / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_text)

    return str(filepath)


def export_delayed_to_csv(delayed_df: pd.DataFrame, output_dir: str = None) -> str:
    """Dump delayed samples to CSV for further analysis. Returns file path."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "reports"

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"delayed_samples_{timestamp}.csv"
    filepath = output_path / filename

    delayed_df.to_csv(filepath, index=False)

    return str(filepath)
