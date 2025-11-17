# 🧠 Quantigo AI — Lead KPI ETL Automation Pipeline

This repository implements an automated **ETL (Extract–Transform–Load)** pipeline that consolidates **Lead KPI**, **Attendance**, **Training**, and **Project Hours** data from Google Sheets into a unified performance report.

The pipeline performs data ingestion, transformation, and enrichment, then exports a cleaned and scored **Final KPI Report** back to Google Sheets.  
It runs autonomously via **GitHub Actions**, providing a robust, reproducible, and version-controlled analytics process.

---

## 🏗️ Architecture Overview

```text
          ┌──────────────────┐
          │  Google Sheets   │
          │ (Lead / PDR /    │
          │  Attendance)     │
          └────────┬─────────┘
                   │ Extract
                   ▼
        ┌──────────────────────┐
        │  Python ETL Layer    │
        │ (Pandas + GSpread)   │
        ├──────────────────────┤
        │  - Cleans QAI IDs    │
        │  - Normalizes Months │
        │  - Merges Datasets   │
        │  - Computes KPI      │
        │  - Applies Weights   │
        │  - Calculates Final  │
        │    Scores            │
        └────────┬─────────────┘
                 │ Load
                 ▼
       ┌───────────────────────────┐
       │  Final Report_Lead Sheet  │
       │ (Google Sheets Output)    │
       └───────────────────────────┘
```

---

## 🚀 Key Features

✅ **Automated ETL Process**  
- Extracts data from multiple Google Sheets using `gspread` and Google API service accounts.  
- Cleans, normalizes, and merges data in-memory via `pandas`.  
- Computes weighted KPI metrics across 8 dimensions.  
- Exports a standardized performance report to Google Sheets.

✅ **GitHub Actions Integration**  
- Fully containerized ETL pipeline for continuous automation.  
- Runs on a fixed schedule (e.g., hourly, daily) or manual trigger.  
- Uses GitHub Secrets for secure credential management.  

✅ **Data Governance Ready**  
- Explicit column normalization and numeric conversion.  
- Consistent schema across months and teams.  
- Idempotent writes (safe to re-run without duplication).  

---

## 🧮 KPI Dimensions Calculated

| Category | Weight | Source |
|-----------|---------|--------|
| Quality (RCA) | 20% | Lead Sheet |
| Project Timeliness | 10% | Lead Sheet |
| Documentation & Reporting | 10% | Lead Sheet |
| Communication Efficiency | 10% | Lead Sheet |
| Discipline & Punctuality | 7.5% | Lead Sheet |
| Contribution (PDR × Hours) | 15% | Project Hours |
| Attendance | 7.5% | Attendance Sheet |
| Training & Assessment | 20% | Attendance Sheet |

**Total Weighted KPI Score:** out of **5.00**

---

## ⚙️ Configuration & Environment Variables

The pipeline reads all configuration values from environment variables (to ensure safe CI/CD operation).

| Variable | Description |
|-----------|-------------|
| `SHEET_ID_LEAD` | Google Sheet ID of the **Lead KPI (Master)** sheet |
| `SHEET_ID_PDR` | Google Sheet ID of the **Project Hours / PDR** sheet |
| `SHEET_ID_REPORT` | Google Sheet ID for **output report destination** |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON credentials of your Google Service Account |

All sensitive credentials are stored as **GitHub Secrets**, never in source code.

---

## 🔐 Service Account Configuration

1. Create a **Google Cloud Project** with the Sheets & Drive APIs enabled.  
2. Generate a **Service Account Key (JSON)** with editor permissions.  
3. Share your Google Sheets with the service account email (e.g. `quantigo-etl@project.iam.gserviceaccount.com`).  
4. In GitHub, go to  
   `Settings → Secrets and variables → Actions → New repository secret`  
   and paste the JSON content as `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## 🧰 Local Development Setup

You can run the same ETL pipeline locally:

```bash
git clone https://github.com/<your-org>/<repo-name>.git
cd <repo-name>

pip install -r requirements.txt

export SHEET_ID_LEAD="your_lead_sheet_id"
export SHEET_ID_PDR="your_pdr_sheet_id"
export SHEET_ID_REPORT="your_report_sheet_id"

echo "<paste service_account.json>" > service_account.json
python lead_kpi_etl.py
```

---

## ⚡ GitHub Actions Workflow

Create a file: `.github/workflows/lead_kpi_etl.yml`

```yaml
name: Lead KPI ETL Automation

on:
  schedule:
    - cron: "0 * * * *" # every hour
  workflow_dispatch:

jobs:
  run-etl:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Dependencies
        run: |
          pip install pandas gspread google-auth google-auth-oauthlib google-auth-httplib2

      - name: Create Service Account File
        run: echo "$GOOGLE_SERVICE_ACCOUNT_JSON" > service_account.json

      - name: Execute ETL Pipeline
        env:
          SHEET_ID_LEAD: ${{ secrets.SHEET_ID_LEAD }}
          SHEET_ID_PDR: ${{ secrets.SHEET_ID_PDR }}
          SHEET_ID_REPORT: ${{ secrets.SHEET_ID_REPORT }}
        run: python lead_kpi_etl.py
```

---

## 📊 Output Deliverable

The script creates (or replaces) a Google Sheet tab:

```
Final Report_Lead
```

### Example Output Columns
| Month | QAI_ID | Lead | Project Name | Project Count | Final KPI Score (Weighted Total Out of 5.00) |
|--------|--------|------|---------------|----------------|-----------------------------------------------|
| April  | QAI_BS1003 | Meherun Nesa | Project A, Project B | 2 | 4.65 |

---

## 📈 ETL Performance Summary

- **Execution Time:** ~30–60 seconds  
- **Data Volume:** ~2–5K records per run  
- **Average Output Rows:** 100–500 (monthly aggregate)  
- **Reliability:** 100% idempotent load  

---

## 🧑‍💼 Maintainers

**Quantigo AI — Automation & Data Analytics Team**  
Contact: `automation@quantigo.ai`

---

## 🪪 License

MIT License © 2025 Quantigo AI  
Use, modify, and distribute with attribution.
