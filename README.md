# 🔬 LIMS Workflow Automation Tool

Automates sample delay detection and reporting for labs running LIMS (like LabVantage).

I built this because in most labs, tracking delayed samples is still a manual process — someone runs a SQL query, eyeballs the results, and maybe sends an email. This tool handles all of that automatically.

---

## Why I Built This

Working with LIMS systems, I kept seeing the same problem: samples move through stages (RECEIVED → IN_PROGRESS → COMPLETED), but when something gets stuck, nobody notices until it's too late. Lab managers end up writing ad-hoc SQL queries to find bottlenecks, and there's no easy way to get a quick daily overview.

So I built a tool that loads sample data, flags anything that's been sitting too long, and spits out a clean report — with an optional AI summary on top.

---

## What It Does

- Loads sample data (CSV) into SQLite and runs delay detection via SQL
- Flags samples that haven't moved past their expected turnaround time
- Breaks down delays by department, test type, and priority
- Generates a formatted daily report (text + optional OpenAI summary)
- Streamlit dashboard for visual exploration and CSV upload

---

## Project Structure

```
lims_workflow_tool/
├── app.py                      # Streamlit dashboard
├── main.py                     # CLI entry point
├── requirements.txt
├── data/
│   └── sample_data.csv         # 40 sample records
├── db/
│   └── database.py             # All SQLite operations
├── core/
│   ├── report_generator.py     # Report formatting & export
│   └── ai_summary.py           # Rule-based + OpenAI summaries
└── reports/                    # Auto-generated reports land here
```

---

## Getting Started

### Install

```bash
cd lims_workflow_tool
pip install -r requirements.txt
```

### CLI

```bash
python main.py                              # default sample data
python main.py --csv path/to/data.csv       # your own data
python main.py --threshold 5                # 5-day delay threshold
python main.py --save-report                # save report to file
python main.py --ai-summary                 # needs OPENAI_API_KEY env var
```

### Streamlit Dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## How Delay Detection Works

The core logic is a SQL UPDATE that checks: if a sample isn't COMPLETED and has been in the system longer than the threshold, mark it delayed.

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

Then aggregation queries break it down by priority, department, and test type — the stuff lab managers actually care about.

---

## CSV Format

| Column | Required | Example |
|--------|----------|---------|
| `sample_id` | ✅ | S001 |
| `request_id` | ✅ | REQ-101 |
| `test_type` | ✅ | Blood Test |
| `status` | ✅ | RECEIVED / IN_PROGRESS / COMPLETED |
| `priority` | ❌ | NORMAL / HIGH / URGENT |
| `department` | ❌ | Hematology |
| `created_date` | ✅ | 2026-04-01 08:00:00 |
| `updated_date` | ✅ | 2026-04-02 14:30:00 |

---

## LabVantage Mapping

The schema is modeled after real LabVantage tables:

| This Project | LabVantage |
|-------------|------------|
| `samples` table | `s_sample` |
| `sample_id` | `s_sampleid` |
| `request_id` | `s_sdcid` |
| `status` | `s_sample.status` |
| `test_type` | `s_test.testid` |
| `created_date` | `s_sample.createdt` |
| Delay detection SQL | Custom SQL reports |
| Report generation | Report Builder |

---

## What I Learned

- Writing SQL that mirrors real LIMS queries (date math, CASE logic, priority ordering)
- Structuring a Python project with clean separation between DB, logic, and UI
- Building a Streamlit dashboard that's actually useful, not just a demo
- Thinking about lab workflows from a manager's perspective — what info do they need and when

---

## Tech Stack

Python · SQLite · Pandas · Streamlit · Plotly · OpenAI (optional)

---

## License

Portfolio project — built for learning and demonstration.
