"""
Streamlit dashboard for the LIMS tool.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent))

from db.database import (
    get_connection,
    create_tables,
    load_csv_to_db,
    run_delay_detection,
    get_summary_stats,
    get_delayed_samples,
    get_all_samples,
    get_sample_lifecycle,
)
from core.report_generator import generate_daily_summary, export_delayed_to_csv
from core.ai_summary import generate_rule_based_summary, generate_openai_summary

# ─── Page config ───
st.set_page_config(
    page_title="LIMS Workflow Automation Tool",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Styling ───
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A5F;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric > div {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        border-left: 4px solid #1E3A5F;
    }
    .delayed-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .status-received { color: #3498db; font-weight: bold; }
    .status-in-progress { color: #f39c12; font-weight: bold; }
    .status-completed { color: #27ae60; font-weight: bold; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Set defaults for session state keys if they don't exist yet."""
    if 'db_conn' not in st.session_state:
        st.session_state.db_conn = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'stats' not in st.session_state:
        st.session_state.stats = None
    if 'delayed_df' not in st.session_state:
        st.session_state.delayed_df = None
    if 'all_samples_df' not in st.session_state:
        st.session_state.all_samples_df = None


def load_data(csv_path: str, threshold: int) -> bool:
    """Spin up an in-memory DB, load the CSV, run delay detection."""
    try:
        conn = get_connection(":memory:")
        create_tables(conn)
        record_count = load_csv_to_db(csv_path, conn)
        delayed_count = run_delay_detection(conn, threshold_days=threshold)

        st.session_state.db_conn = conn
        st.session_state.data_loaded = True
        st.session_state.stats = get_summary_stats(conn)
        st.session_state.delayed_df = get_delayed_samples(conn)
        st.session_state.all_samples_df = get_all_samples(conn)

        return True
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return False


def render_sidebar():
    """Sidebar: data source picker, threshold slider, analyze button."""
    st.sidebar.markdown("## ⚙️ Configuration")

    st.sidebar.markdown("### 📂 Data Source")
    data_source = st.sidebar.radio(
        "Choose data source:",
        ["Use Sample Data", "Upload CSV"],
        index=0,
    )

    csv_path = None
    uploaded_file = None

    if data_source == "Use Sample Data":
        csv_path = str(Path(__file__).parent / 'data' / 'sample_data.csv')
        st.sidebar.success("Using built-in sample dataset (40 samples)")
    else:
        uploaded_file = st.sidebar.file_uploader(
            "Upload your CSV file",
            type=['csv'],
            help="CSV must have columns: sample_id, request_id, test_type, status, created_date, updated_date"
        )

    st.sidebar.markdown("### ⏱️ Delay Threshold")
    threshold = st.sidebar.slider(
        "Days before marking as delayed:",
        min_value=1,
        max_value=14,
        value=3,
        help="Samples not completed within this many days will be flagged"
    )

    st.sidebar.markdown("---")
    process_clicked = st.sidebar.button(
        "🚀 Analyze Samples",
        use_container_width=True,
        type="primary",
    )

    if process_clicked:
        if data_source == "Upload CSV" and uploaded_file is not None:
            # Write uploaded file to a temp location so we can pass a path
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w') as f:
                f.write(uploaded_file.getvalue().decode('utf-8'))
                csv_path = f.name

        if csv_path:
            with st.spinner("Analyzing samples..."):
                success = load_data(csv_path, threshold)
                if success:
                    st.sidebar.success(f"✅ Analysis complete!")
                    if data_source == "Upload CSV" and csv_path and os.path.exists(csv_path):
                        os.unlink(csv_path)
        else:
            st.sidebar.warning("Please upload a CSV file first.")

    # Optional OpenAI key
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🤖 AI Summary (Optional)")
    api_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        help="Optional: for AI-powered summaries instead of rule-based ones"
    )

    return threshold, api_key


def render_dashboard():
    """Main dashboard tab — metrics cards and charts."""
    stats = st.session_state.stats
    delayed_df = st.session_state.delayed_df
    all_df = st.session_state.all_samples_df

    st.markdown("### 📊 Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total Samples", stats['total_samples'])
    with col2:
        st.metric("✅ Completed", stats['completed'])
    with col3:
        st.metric("🔄 In Progress", stats['in_progress'])
    with col4:
        st.metric("📥 Received", stats['received'])
    with col5:
        st.metric(
            "⚠️ Delayed",
            stats['delayed'],
            delta=f"-{stats['delayed']}" if stats['delayed'] > 0 else None,
            delta_color="inverse"
        )

    if stats['total_samples'] > 0:
        completion_rate = stats['completed'] / stats['total_samples']
        st.progress(completion_rate, text=f"Completion Rate: {completion_rate*100:.1f}%")

    st.markdown("---")

    # ─── Charts ───
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("#### Sample Status Distribution")
        status_data = pd.DataFrame({
            'Status': ['COMPLETED', 'IN_PROGRESS', 'RECEIVED'],
            'Count': [stats['completed'], stats['in_progress'], stats['received']],
        })
        fig_pie = px.pie(
            status_data,
            values='Count',
            names='Status',
            color='Status',
            color_discrete_map={
                'COMPLETED': '#27ae60',
                'IN_PROGRESS': '#f39c12',
                'RECEIVED': '#3498db',
            },
        )
        fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20))
        st.plotly_chart(fig_pie, width='stretch')

    with chart_col2:
        st.markdown("#### Delays by Department")
        if stats.get('delayed_by_department'):
            dept_data = pd.DataFrame(
                list(stats['delayed_by_department'].items()),
                columns=['Department', 'Delayed Count']
            )
            fig_bar = px.bar(
                dept_data,
                x='Department',
                y='Delayed Count',
                color='Delayed Count',
                color_continuous_scale='Reds',
            )
            fig_bar.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_bar, width='stretch')
        else:
            st.info("No delays to display by department.")

    chart_col3, chart_col4 = st.columns(2)

    with chart_col3:
        st.markdown("#### Delays by Priority")
        if stats.get('delayed_by_priority'):
            priority_data = pd.DataFrame(
                list(stats['delayed_by_priority'].items()),
                columns=['Priority', 'Count']
            )
            fig_priority = px.bar(
                priority_data,
                x='Priority',
                y='Count',
                color='Priority',
                color_discrete_map={
                    'URGENT': '#e74c3c',
                    'HIGH': '#f39c12',
                    'NORMAL': '#27ae60',
                },
            )
            fig_priority.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_priority, width='stretch')
        else:
            st.info("No delays to display by priority.")

    with chart_col4:
        st.markdown("#### Delays by Test Type")
        if stats.get('delayed_by_test_type'):
            test_data = pd.DataFrame(
                list(stats['delayed_by_test_type'].items()),
                columns=['Test Type', 'Count']
            )
            fig_test = px.bar(
                test_data,
                x='Test Type',
                y='Count',
                color='Count',
                color_continuous_scale='OrRd',
            )
            fig_test.update_layout(
                margin=dict(t=20, b=20, l=20, r=20),
                xaxis_tickangle=-45,
            )
            st.plotly_chart(fig_test, width='stretch')
        else:
            st.info("No delays to display by test type.")


def render_delayed_samples():
    """Delayed samples tab — stats + color-coded table + CSV download."""
    delayed_df = st.session_state.delayed_df
    stats = st.session_state.stats

    st.markdown("### ⚠️ Delayed Samples")

    if delayed_df.empty:
        st.success("🎉 No delayed samples! All samples are on track.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Delayed", stats['delayed'])
    with col2:
        st.metric("Avg Delay (days)", stats['avg_delay_days'])
    with col3:
        st.metric("Max Delay (days)", stats['max_delay_days'])

    st.markdown("#### Delayed Samples Detail")

    def highlight_priority(val):
        if val == 'URGENT':
            return 'background-color: #ffcccc; color: #cc0000; font-weight: bold'
        elif val == 'HIGH':
            return 'background-color: #fff3cd; color: #856404; font-weight: bold'
        return ''

    def highlight_delay(val):
        try:
            v = float(val)
            if v > 10:
                return 'background-color: #ffcccc; font-weight: bold'
            elif v > 5:
                return 'background-color: #fff3cd'
        except (ValueError, TypeError):
            pass
        return ''

    styled_df = delayed_df.style.map(
        highlight_priority, subset=['priority']
    ).map(
        highlight_delay, subset=['delay_days']
    )

    st.dataframe(styled_df, width='stretch', hide_index=True)

    csv_data = delayed_df.to_csv(index=False)
    st.download_button(
        label="📥 Download Delayed Samples CSV",
        data=csv_data,
        file_name=f"delayed_samples_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


def render_all_samples():
    """All samples tab — filterable table."""
    all_df = st.session_state.all_samples_df

    st.markdown("### 📋 All Samples")

    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        status_filter = st.multiselect(
            "Filter by Status",
            options=['RECEIVED', 'IN_PROGRESS', 'COMPLETED'],
            default=['RECEIVED', 'IN_PROGRESS', 'COMPLETED'],
        )

    with filter_col2:
        priority_filter = st.multiselect(
            "Filter by Priority",
            options=sorted(all_df['priority'].unique()),
            default=sorted(all_df['priority'].unique()),
        )

    with filter_col3:
        dept_filter = st.multiselect(
            "Filter by Department",
            options=sorted(all_df['department'].unique()),
            default=sorted(all_df['department'].unique()),
        )

    filtered_df = all_df[
        (all_df['status'].isin(status_filter)) &
        (all_df['priority'].isin(priority_filter)) &
        (all_df['department'].isin(dept_filter))
    ]

    st.markdown(f"Showing **{len(filtered_df)}** of **{len(all_df)}** samples")

    def color_status(val):
        colors = {
            'RECEIVED': 'color: #3498db; font-weight: bold',
            'IN_PROGRESS': 'color: #f39c12; font-weight: bold',
            'COMPLETED': 'color: #27ae60; font-weight: bold',
        }
        return colors.get(val, '')

    def color_delayed(val):
        if val == 1:
            return 'background-color: #ffcccc; font-weight: bold'
        return ''

    styled = filtered_df.style.map(
        color_status, subset=['status']
    ).map(
        color_delayed, subset=['is_delayed']
    )

    st.dataframe(styled, width='stretch', hide_index=True)


def render_report(threshold: int, api_key: str):
    """Report tab — full text report + AI summary."""
    stats = st.session_state.stats
    delayed_df = st.session_state.delayed_df

    st.markdown("### 📝 Generated Report")

    tab1, tab2 = st.tabs(["📄 Full Report", "🤖 AI Summary"])

    with tab1:
        report = generate_daily_summary(stats, delayed_df, threshold)
        st.text(report)

        st.download_button(
            label="📥 Download Report",
            data=report,
            file_name=f"lims_report_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
        )

    with tab2:
        if api_key:
            summary = generate_openai_summary(stats, delayed_df, api_key)
        else:
            summary = generate_rule_based_summary(stats, delayed_df)

        st.markdown(summary)


def render_sample_lifecycle():
    """Lifecycle tab — pick a sample and see where it is in the pipeline."""
    st.markdown("### 🔄 Sample Lifecycle Tracker")

    all_df = st.session_state.all_samples_df

    sample_id = st.selectbox(
        "Select a sample to view its lifecycle:",
        options=all_df['sample_id'].tolist(),
    )

    if sample_id and st.session_state.db_conn:
        sample = get_sample_lifecycle(st.session_state.db_conn, sample_id)

        if sample:
            col1, col2 = st.columns([1, 2])

            with col1:
                st.markdown("#### Sample Details")
                st.markdown(f"**Sample ID:** {sample['sample_id']}")
                st.markdown(f"**Request ID:** {sample['request_id']}")
                st.markdown(f"**Test Type:** {sample['test_type']}")
                st.markdown(f"**Department:** {sample['department']}")
                st.markdown(f"**Priority:** {sample['priority']}")
                st.markdown(f"**Created:** {sample['created_date']}")
                st.markdown(f"**Updated:** {sample['updated_date']}")

                if sample['is_delayed']:
                    st.error(f"⚠️ DELAYED — {sample['delay_days']} days")
                else:
                    st.success("✅ On Track")

            with col2:
                st.markdown("#### Lifecycle Progress")

                stages = ['RECEIVED', 'IN_PROGRESS', 'COMPLETED']
                current_status = sample['status']
                current_idx = stages.index(current_status) if current_status in stages else 0

                # Show each stage as a step indicator
                cols = st.columns(len(stages))
                for i, stage in enumerate(stages):
                    with cols[i]:
                        if i < current_idx:
                            st.markdown(f"✅ **{stage}**")
                            st.markdown("*Completed*")
                        elif i == current_idx:
                            if stage == 'COMPLETED':
                                st.markdown(f"✅ **{stage}**")
                                st.markdown("*Done*")
                            else:
                                st.markdown(f"🔄 **{stage}**")
                                st.markdown("*Current*")
                        else:
                            st.markdown(f"⬜ **{stage}**")
                            st.markdown("*Pending*")

                st.markdown("#### Timeline")
                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=[sample['created_date'], sample['updated_date']],
                    y=[1, 1],
                    mode='markers+lines+text',
                    text=['Created', f'Last Update ({current_status})'],
                    textposition='top center',
                    marker=dict(size=15, color=['#3498db', '#27ae60' if current_status == 'COMPLETED' else '#f39c12']),
                    line=dict(color='#95a5a6', width=2),
                ))

                fig.update_layout(
                    height=150,
                    margin=dict(t=40, b=20, l=20, r=20),
                    yaxis=dict(visible=False),
                    xaxis=dict(title='Date'),
                    showlegend=False,
                )
                st.plotly_chart(fig, width='stretch')


def main():
    init_session_state()

    st.markdown('<div class="main-header">🔬 LIMS Workflow Automation Tool</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">'
        'Track sample lifecycle • Detect delays • Generate reports'
        '</div>',
        unsafe_allow_html=True,
    )

    threshold, api_key = render_sidebar()

    if not st.session_state.data_loaded:
        st.markdown("---")
        st.markdown("""
        ### 👋 Welcome!

        This tool helps lab managers and LIMS administrators:

        1. **📂 Load sample data** from CSV files (simulating LIMS exports)
        2. **🔍 Detect delayed samples** using configurable thresholds
        3. **📊 Visualize** sample status distribution and delay patterns
        4. **📝 Generate reports** for daily standup meetings
        5. **🤖 Get AI summaries** of lab operations

        ---

        #### 🚀 Getting Started

        1. Choose a data source in the sidebar (or use the built-in sample data)
        2. Set your delay threshold (default: 3 days)
        3. Click **"Analyze Samples"** to begin

        ---

        #### 📋 Expected CSV Format

        Your CSV file should have these columns:

        | Column | Description | Example |
        |--------|-------------|---------|
        | `sample_id` | Unique sample identifier | S001 |
        | `request_id` | Lab request/order ID | REQ-101 |
        | `test_type` | Type of test | Blood Test |
        | `status` | Current status | RECEIVED / IN_PROGRESS / COMPLETED |
        | `priority` | Priority level (optional) | NORMAL / HIGH / URGENT |
        | `department` | Lab department (optional) | Hematology |
        | `created_date` | When sample was created | 2026-04-01 08:00:00 |
        | `updated_date` | Last status update | 2026-04-02 14:30:00 |
        """)
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Dashboard",
            "⚠️ Delayed Samples",
            "📋 All Samples",
            "🔄 Lifecycle",
            "📝 Report",
        ])

        with tab1:
            render_dashboard()
        with tab2:
            render_delayed_samples()
        with tab3:
            render_all_samples()
        with tab4:
            render_sample_lifecycle()
        with tab5:
            render_report(threshold, api_key)

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #999; font-size: 0.8rem;'>"
        "LIMS Workflow Automation Tool | Built with Python, SQLite, Pandas & Streamlit"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
