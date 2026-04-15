# 🔬 LIMS Workflow Automation Tool

A practical project that simulates real-world **LabVantage LIMS operations** — tracking sample lifecycle, detecting delays, and generating automated reports.

Built to demonstrate real **LIMS domain knowledge**, **SQL proficiency**, **Python backend skills**, and **workflow automation** capabilities.

---

## 📌 Problem Statement

In many laboratories using LIMS (Laboratory Information Management Systems) like LabVantage:

- Samples move through stages: **RECEIVED → IN_PROGRESS → COMPLETED**
- Delays happen frequently but are tracked **manually** using ad-hoc SQL queries
- Lab managers lack **real-time visibility** into bottlenecks
- There's no automated alerting when samples exceed expected turnaround times

**This tool automates delay detection and reporting**, saving hours of manual work and improving lab efficiency.

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| **Sample Data Simulation** | Realistic dataset mimicking LabVantage LIMS tables |
| **SQLite Database** | Proper database schema with SQL queries (not just CSV processing) |
| **Delay Detection** | Automated flagging of samples exceeding configurable thresholds |
| **Report Generation** | Formatted daily summary with status breakdown and delay analysis |
| **AI Summary** | Natural language summary of lab status (rule-based + optional OpenAI) |
| **Interactive Dashboard** | Streamlit UI with charts, filters, and lifecycle visualization |
| **CSV Upload** | Upload your own data for analysis |

---

## 🏗️ Project Structure

```
lims_workflow_tool/
├── app.py                      # Streamlit web application
├── main.py                     # CLI entry point
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── data/
│   └── sample_data.csv         # Sample dataset (40 records)
├── db/
│   ├── __init__.py
│   └── database.py             # SQLite database operations & SQL queries
├── core/
│   ├── __init__.py
│   ├── report_generator.py     # Report formatting & export
│   └── ai_summary.py           # AI/rule-based summary generation
└── reports/                    # Generated reports (auto-created)
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd lims_workflow_tool
pip install -r requirements.txt
```

### 2. Run CLI Version

```bash
# Use default sample data
python main.py

# Custom CSV with 5-day threshold
python main.py --csv path/to/your/data.csv --threshold 5

# Save report to file
python main.py --save-report

# With AI summary (requires OPENAI_API_KEY env variable)
python main.py --ai-summary
```

### 3. Run Streamlit Dashboard

```bash
cd lims_workflow_tool
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

---

## 📊 Sample Data Format

The tool expects CSV files with these columns:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `sample_id` | Text | ✅ | Unique sample identifier (e.g., S001) |
| `request_id` | Text | ✅ | Lab request/order ID (e.g., REQ-101) |
| `test_type` | Text | ✅ | Type of test (e.g., Blood Test, CBC) |
| `status` | Text | ✅ | RECEIVED, IN_PROGRESS, or COMPLETED |
| `priority` | Text | ❌ | NORMAL, HIGH, or URGENT (default: NORMAL) |
| `department` | Text | ❌ | Lab department (default: General) |
| `created_date` | DateTime | ✅ | When sample entered the system |
| `updated_date` | DateTime | ✅ | Last status update timestamp |

---

## 🔧 Technical Details

### Database Schema (SQLite)

```sql
CREATE TABLE samples (
    sample_id       TEXT PRIMARY KEY,
    request_id      TEXT NOT NULL,
    test_type       TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('RECEIVED', 'IN_PROGRESS', 'COMPLETED')),
    priority        TEXT DEFAULT 'NORMAL',
    department      TEXT,
    created_date    TIMESTAMP NOT NULL,
    updated_date    TIMESTAMP NOT NULL,
    is_delayed      INTEGER DEFAULT 0,
    delay_days      REAL DEFAULT 0
);
```

### Key SQL Queries Used

**Delay Detection:**
```sql
UPDATE samples
SET is_delayed = CASE
        WHEN status != 'COMPLETED'
             AND julianday(?) - julianday(created_date) > ?
        THEN 1 ELSE 0
    END,
    delay_days = CASE
        WHEN status != 'COMPLETED'
             AND julianday(?) - julianday(created_date) > ?
        THEN ROUND(julianday(?) - julianday(created_date), 1)
        ELSE 0
    END
```

**Summary Statistics:**
```sql
SELECT
    COUNT(*) as total_samples,
    SUM(CASE WHEN status = 'RECEIVED' THEN 1 ELSE 0 END) as received,
    SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN is_delayed = 1 THEN 1 ELSE 0 END) as delayed
FROM samples
```

**Delayed Samples by Priority:**
```sql
SELECT priority, COUNT(*) as cnt
FROM samples
WHERE is_delayed = 1
GROUP BY priority
ORDER BY CASE priority
    WHEN 'URGENT' THEN 1
    WHEN 'HIGH' THEN 2
    WHEN 'NORMAL' THEN 3
END
```

---

## 🗣️ How to Explain This Project in Interviews

### The Elevator Pitch (30 seconds)

> "I built a LIMS Workflow Automation Tool that simulates real lab operations. It loads sample data into SQLite, tracks the lifecycle of each sample through RECEIVED, IN_PROGRESS, and COMPLETED stages, and automatically detects delays using SQL queries. It generates daily reports and even provides AI-powered summaries. I built it using Python, SQL, Pandas, and Streamlit — the same skills used in real LabVantage implementations."

### Detailed Explanation (2-3 minutes)

**The Problem:**
> "In labs using LabVantage LIMS, samples go through multiple stages. When delays happen — say a blood test sits in IN_PROGRESS for 5 days — it's usually caught manually by running SQL queries or checking reports. This is time-consuming and error-prone."

**My Solution:**
> "I built a tool that automates this entire process. It:
> 1. Takes sample data (simulating a LIMS export) and loads it into a SQLite database
> 2. Runs SQL queries to detect which samples have exceeded the expected turnaround time
> 3. Generates a comprehensive report breaking down delays by department, test type, and priority
> 4. Provides a natural language summary that a lab manager can use in daily meetings
> 5. Has an interactive dashboard built with Streamlit for visual analysis"

**Technical Depth:**
> "The SQL queries I wrote mirror what you'd actually run in LabVantage — using date functions to calculate delays, CASE statements for conditional logic, GROUP BY for aggregations, and proper ordering by business priority. The database schema is modeled after the LabVantage s_sample table structure."

**Business Value:**
> "This tool saves lab managers 30-60 minutes daily by automating delay detection. It also improves sample turnaround times by providing early visibility into bottlenecks — for example, if the Biochemistry department consistently has delays, management can allocate more resources there."

### Common Interview Questions & Answers

**Q: Why did you choose SQLite?**
> "SQLite is perfect for this project because it's serverless, requires no setup, and supports standard SQL. In production, this would connect to the LabVantage Oracle/PostgreSQL database, but the SQL queries would be very similar."

**Q: How does this relate to real LabVantage work?**
> "In LabVantage, samples are tracked in the s_sample table with status fields. Admins regularly run SQL queries to check sample status and identify delays. This tool automates that exact workflow. The data model, status transitions, and reporting logic all mirror real LIMS operations."

**Q: What would you add if you had more time?**
> "I'd add: (1) Email alerts for URGENT delayed samples, (2) Historical trend analysis to predict future delays, (3) Integration with actual LabVantage REST APIs, (4) Role-based access for lab managers vs. technicians, (5) Audit trail logging for compliance."

**Q: How does the AI summary work?**
> "It works in two modes. The default mode uses rule-based logic — analyzing the statistics and generating sentences based on patterns (e.g., 'The Biochemistry department has the most delays'). If an OpenAI API key is provided, it sends the statistics to GPT-3.5 with a carefully crafted prompt to generate a more nuanced summary."

**Q: Can this handle real-world data volumes?**
> "The current version handles hundreds to thousands of samples efficiently. For larger volumes, I'd switch to PostgreSQL, add database indexing on status and created_date columns, and implement pagination in the UI."

---

## 🔗 LabVantage LIMS Connection

This project directly maps to real LabVantage concepts:

| This Project | LabVantage Equivalent |
|-------------|----------------------|
| `samples` table | `s_sample` table |
| `sample_id` | `s_sampleid` |
| `request_id` | `s_sdcid` (Service Request) |
| `status` field | `s_sample.status` |
| `test_type` | `s_test.testid` |
| `created_date` | `s_sample.createdt` |
| Delay detection SQL | Custom SQL reports in LabVantage |
| Report generation | LabVantage Report Builder |
| Status transitions | LabVantage Workflow Engine |

---

## 📝 Skills Demonstrated

- ✅ **LIMS Domain Knowledge** — Understanding of sample lifecycle, lab workflows, and turnaround times
- ✅ **SQL Proficiency** — Complex queries with JOINs, CASE statements, aggregations, date functions
- ✅ **Python Backend** — Clean, modular code with proper error handling
- ✅ **Data Processing** — Pandas for data manipulation and analysis
- ✅ **Database Design** — Proper schema with constraints and data types
- ✅ **Web Development** — Interactive dashboard with Streamlit
- ✅ **Data Visualization** — Charts and graphs with Plotly
- ✅ **AI Integration** — Optional OpenAI API integration
- ✅ **Problem Solving** — Identifying and automating a real business problem
- ✅ **Documentation** — Clear README, code comments, and interview preparation

---

## 📄 License

This project is for educational and portfolio purposes.

---

## 👤 Author

Built as a portfolio project to demonstrate LIMS workflow automation skills.
