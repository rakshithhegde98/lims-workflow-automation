# 🔬 LIMS Sample Delay & Bottleneck Dashboard

Automates sample delay detection and reporting for labs using LIMS (like LabVantage).

I built this because in most labs, tracking delayed samples is still manual — someone runs a SQL query, scans results, and maybe sends an email. This tool removes that manual step.

---

## Why I Built This

While working with LIMS systems, I kept seeing the same issue:

Samples move through stages (RECEIVED → IN_PROGRESS → COMPLETED), but when something gets stuck, it’s not immediately visible. By the time someone checks, it’s already delayed.

Most teams rely on ad-hoc SQL queries to find these issues, and there’s no simple way to get a quick daily view.

So I built a tool that:

* loads sample data
* flags delays automatically
* generates a clean daily report

---

## What It Does

* Loads sample data (CSV → SQLite)
* Flags samples exceeding turnaround time
* Breaks down delays by:

  * department
  * test type
  * priority
* Generates a daily report (text + optional AI summary)
* Includes a Streamlit dashboard for exploration

---

## Project Structure

```
lims_workflow_tool/
├── app.py                      # Streamlit dashboard
├── main.py                     # CLI entry point
├── requirements.txt
├── data/
│   └── sample_data.csv
├── db/
│   └── database.py             # DB + SQL logic
├── core/
│   ├── report_generator.py
│   └── ai_summary.py
└── reports/                    # generated reports
```

---

## Getting Started

### Install

```
cd lims_workflow_tool
pip install -r requirements.txt
```

---

### CLI

```
python main.py
python main.py --csv path/to/data.csv
python main.py --threshold 5
python main.py --save-report
python main.py --ai-summary   # requires OPENAI_API_KEY
```

---

### Streamlit Dashboard

```
streamlit run app.py
```

Runs at: http://localhost:8501

---

## How Delay Detection Works

Core idea is simple:

* If sample is not COMPLETED
* And it's older than threshold
  → mark it as delayed

Implemented using SQL:

```
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

Then aggregation queries break delays down by priority, department, and test type.

---

## CSV Format

| Column       | Required | Example                            |
| ------------ | -------- | ---------------------------------- |
| sample_id    | ✅        | S001                               |
| request_id   | ✅        | REQ-101                            |
| test_type    | ✅        | Blood Test                         |
| status       | ✅        | RECEIVED / IN_PROGRESS / COMPLETED |
| priority     | ❌        | NORMAL / HIGH / URGENT             |
| department   | ❌        | Hematology                         |
| created_date | ✅        | 2026-04-01 08:00:00                |
| updated_date | ✅        | 2026-04-02 14:30:00                |

---

## LabVantage Mapping

This is loosely modeled around real LabVantage concepts:

| This Project      | LabVantage        |
| ----------------- | ----------------- |
| samples table     | s_sample          |
| sample_id         | s_sampleid        |
| request_id        | s_sdcid           |
| status            | s_sample.status   |
| test_type         | s_test.testid     |
| created_date      | s_sample.createdt |
| delay detection   | custom SQL report |
| report generation | report builder    |

---

## What I Learned

* Writing SQL similar to real LIMS reporting (date logic, CASE, grouping)
* Structuring a Python project (DB layer, logic layer, UI)
* Building a Streamlit dashboard that’s actually usable
* Thinking in terms of lab operations, not just code

---

## Tech Stack

Python · SQLite · Pandas · Streamlit · Plotly · OpenAI (optional)

---

## Note

This is a portfolio project built to simulate real LIMS workflows and automation use cases.
