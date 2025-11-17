# 📊 KPI Automation ETL Pipeline

This repository contains an automated **ETL (Extract–Transform–Load)** pipeline for generating Key Performance Indicator (KPI) reports directly from structured data stored in Google Sheets.  
The system consolidates multiple data sources, applies defined transformation logic, and publishes a final KPI report back to Google Sheets — all fully automated using **GitHub Actions**.

---

## 🧩 Overview

```text
        ┌────────────────────────┐
        │  Source Google Sheets   │
        │ (e.g., Projects, Data,  │
        │  Attendance, Metrics)   │
        └──────────┬──────────────┘
                   │ Extract
                   ▼
        ┌────────────────────────┐
        │   Python ETL Workflow   │
        │ (Pandas + GSpread API)  │
        ├────────────────────────┤
        │ - Data Cleaning         │
        │ - Normalization         │
        │ - Aggregation           │
        │ - KPI Calculations      │
        │ - Report Structuring    │
        └──────────┬──────────────┘
                   │ Load
                   ▼
        ┌────────────────────────┐
        │  KPI Report (Google     │
        │  Sheets Output)         │
        └────────────────────────┘
```

---

## 🚀 Key Features

- **Automated ETL Pipeline** — Extracts, transforms, and loads data from Google Sheets.  
- **KPI Computation Framework** — Calculates performance metrics using configurable weighting and aggregation.  
- **Scheduled Execution** — Runs automatically via GitHub Actions (hourly, daily, or on demand).  
- **Cloud-Native Design** — No local dependencies required once deployed.  
- **Secure Configuration** — Uses GitHub Secrets for all credentials and environment variables.  
- **Idempotent Processing** — Safe for repeated executions without duplication.

---

## ⚙️ Configuration

The script uses environment variables to define its input/output sources and credentials.

| Environment Variable | Description |
|----------------------|-------------|
| `SHEET_ID_SOURCE` | Google Sheet ID containing raw KPI data |
| `SHEET_ID_OUTPUT` | Google Sheet ID where the final KPI report is exported |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON credentials for a Google Service Account with sheet access |

Store all variables as **GitHub Secrets** — never commit them to the repository.

---

## 🔐 Google Service Account Setup

1. Enable the **Google Sheets API** and **Google Drive API** in the [Google Cloud Console](https://console.cloud.google.com/).  
2. Create a **Service Account**, generate a **JSON key**, and download it.  
3. Share your Google Sheets with the service account email (Editor access).  
4. Add the JSON key content to GitHub Secrets as `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## 🧰 Local Development

You can test or customize the ETL pipeline locally:

```bash
git clone https://github.com/<username>/<repo-name>.git
cd <repo-name>

pip install -r requirements.txt

export SHEET_ID_SOURCE="your_source_sheet_id"
export SHEET_ID_OUTPUT="your_output_sheet_id"

echo "<paste service_account.json>" > service_account.json
python kpi_etl_pipeline.py
```

---

## ⚡ GitHub Actions Workflow

Create a file: `.github/workflows/kpi_etl.yml`

```yaml
name: KPI ETL Automation

on:
  schedule:
    - cron: "0 * * * *" # every hour
  workflow_dispatch:

jobs:
  run-etl:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Dependencies
        run: |
          pip install pandas gspread google-auth google-auth-oauthlib google-auth-httplib2

      - name: Create Service Account File
        run: echo "$GOOGLE_SERVICE_ACCOUNT_JSON" > service_account.json

      - name: Run KPI ETL Script
        env:
          SHEET_ID_SOURCE: ${{ secrets.SHEET_ID_SOURCE }}
          SHEET_ID_OUTPUT: ${{ secrets.SHEET_ID_OUTPUT }}
        run: python kpi_etl_pipeline.py
```

---

## 📊 Output

The ETL pipeline generates or updates a KPI report in the specified destination Google Sheet.  
The report includes aggregated and weighted metrics computed from the source data.

Example output columns:
| Period | ID | Project | Metric 1 | Metric 2 | KPI Score |
|---------|----|----------|-----------|-----------|-----------|
| January | 001 | Sample Project | 82 | 90 | 4.75 |

---

## 🧠 Technical Details

- Language: **Python 3.10+**  
- Libraries: `pandas`, `gspread`, `google-auth`  
- Scheduler: **GitHub Actions (cron + manual trigger)**  
- Runtime: Typically < 1 minute  
- Output Format: Google Sheets Worksheet  

---

## 🧑‍💻 Maintainers

This repository is maintained by the internal data automation team.  
For enhancements or support, please refer to the workflow or script documentation.

---

## 🪪 License

MIT License  
You may use, modify, and distribute this code with attribution.
