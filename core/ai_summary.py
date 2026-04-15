"""
Summary generation — rule-based by default, OpenAI if a key is available.

The rule-based version covers the common patterns (worst department,
urgent flags, etc.) so it's useful even without an API key.
"""

import os
import pandas as pd


def generate_rule_based_summary(stats: dict, delayed_df: pd.DataFrame) -> str:
    """
    Build a plain-English summary from the stats dict.
    No API needed — just pattern matching on the numbers.
    """
    parts = []

    total = stats['total_samples']
    completed = stats['completed']
    delayed = stats['delayed']
    in_progress = stats['in_progress']
    received = stats['received']

    parts.append(f"📋 **Daily Lab Summary**\n")

    completion_pct = (completed / total * 100) if total > 0 else 0
    parts.append(
        f"Today, the lab has **{total} samples** in the system. "
        f"**{completed}** ({completion_pct:.0f}%) have been completed, "
        f"**{in_progress}** are in progress, and **{received}** are awaiting processing."
    )

    if delayed > 0:
        avg_delay = stats.get('avg_delay_days', 0)
        max_delay = stats.get('max_delay_days', 0)

        parts.append(
            f"\n⚠️ **{delayed} sample(s) are delayed**, "
            f"with an average delay of **{avg_delay} days** "
            f"and the longest delay being **{max_delay} days**."
        )

        # Which department is hurting the most
        dept_delays = stats.get('delayed_by_department', {})
        if dept_delays:
            worst_dept = max(dept_delays, key=dept_delays.get)
            worst_count = dept_delays[worst_dept]
            parts.append(
                f"\nThe **{worst_dept}** department is most affected "
                f"with **{worst_count} delayed sample(s)**."
            )

        # Which test type keeps getting stuck
        test_delays = stats.get('delayed_by_test_type', {})
        if test_delays:
            worst_test = max(test_delays, key=test_delays.get)
            worst_test_count = test_delays[worst_test]
            parts.append(
                f"The most commonly delayed test is **{worst_test}** "
                f"({worst_test_count} sample(s))."
            )

        # Call out urgent/high priority stuff — that's what managers want to see
        priority_delays = stats.get('delayed_by_priority', {})
        urgent_count = priority_delays.get('URGENT', 0)
        high_count = priority_delays.get('HIGH', 0)

        if urgent_count > 0:
            parts.append(
                f"\n🔴 **Action Required:** {urgent_count} URGENT sample(s) "
                f"are delayed and need immediate attention."
            )
        if high_count > 0:
            parts.append(
                f"🟡 {high_count} HIGH priority sample(s) are also delayed."
            )

        parts.append(
            f"\n💡 **Recommendation:** Review the {worst_dept} department workflow "
            f"and prioritize clearing the backlog of {worst_test} tests."
        )
    else:
        parts.append(
            "\n✅ **No delays detected!** All samples are progressing within "
            "the expected timeframe. Great job, team!"
        )

    return "\n".join(parts)


def generate_openai_summary(stats: dict, delayed_df: pd.DataFrame,
                            api_key: str = None) -> str:
    """
    Hit OpenAI for a more nuanced summary. Falls back to rule-based
    if no key is set or the call fails.
    """
    key = api_key or os.environ.get('OPENAI_API_KEY')

    if not key:
        return generate_rule_based_summary(stats, delayed_df)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)

        delayed_info = ""
        if not delayed_df.empty:
            delayed_info = delayed_df.to_string(index=False)

        prompt = f"""You are a lab operations analyst. Generate a brief, professional 
summary of the current lab sample status for a daily standup meeting.

Key Statistics:
- Total Samples: {stats['total_samples']}
- Completed: {stats['completed']}
- In Progress: {stats['in_progress']}
- Received (Pending): {stats['received']}
- Delayed: {stats['delayed']}
- Average Delay: {stats.get('avg_delay_days', 0)} days
- Max Delay: {stats.get('max_delay_days', 0)} days

Delayed by Department: {stats.get('delayed_by_department', {})}
Delayed by Test Type: {stats.get('delayed_by_test_type', {})}
Delayed by Priority: {stats.get('delayed_by_priority', {})}

Delayed Samples Detail:
{delayed_info}

Provide:
1. A 2-3 sentence executive summary
2. Key concerns (if any)
3. One actionable recommendation

Keep it concise and professional. Use plain language a lab manager would understand."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful lab operations analyst."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )

        return "🤖 **AI-Generated Summary**\n\n" + response.choices[0].message.content

    except ImportError:
        return (
            "⚠️ OpenAI package not installed. Install with: pip install openai\n\n"
            + generate_rule_based_summary(stats, delayed_df)
        )
    except Exception as e:
        return (
            f"⚠️ OpenAI API error: {str(e)}\n\n"
            "Falling back to rule-based summary:\n\n"
            + generate_rule_based_summary(stats, delayed_df)
        )
