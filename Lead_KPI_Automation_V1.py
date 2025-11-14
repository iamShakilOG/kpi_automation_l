# ============================================================
# Lead KPI Calculation Script (with Attendance & Training + Project Count)
# GitHub Actions Compatible — identical output to local version
# ============================================================

import pandas as pd
import numpy as np
import re
import gspread
from google.oauth2.service_account import Credentials
from pandas import ExcelWriter
from datetime import datetime
import os

# ==== 1) Connect to Google Sheets using Secrets ====
SHEET_ID_LEAD = os.getenv("SHEET_ID_LEAD")
SHEET_ID_PDR = os.getenv("SHEET_ID_PDR")
SHEET_ID_REPORT = os.getenv("SHEET_ID_REPORT")

if not SHEET_ID_LEAD or not SHEET_ID_PDR or not SHEET_ID_REPORT:
    raise ValueError("❌ Missing required Sheet IDs in environment variables!")

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(creds)

# ==== 2) Load Lead KPI Sheet (MASTER) ====
spreadsheet_lead = client.open_by_key(SHEET_ID_LEAD)
ws_lead = spreadsheet_lead.worksheet("Lead")
lead_data = ws_lead.get("B:J")  # B–J: Lead → Discipline & Punctuality
lead_df = pd.DataFrame(lead_data[1:], columns=lead_data[0])
lead_df.columns = lead_df.columns.str.strip()

# ==== 3) Load Project Hours + PDR Sheet ====
spreadsheet_pdr = client.open_by_key(SHEET_ID_PDR)
ws_pdr = spreadsheet_pdr.worksheet("Project_Hours")
pdr_data = ws_pdr.get_all_records()
pdr_df = pd.DataFrame(pdr_data)
pdr_df.columns = pdr_df.columns.str.strip()

# ==== 4) Load Attendance Sheet (from MASTER) ====
ws_att = spreadsheet_lead.worksheet("Attendance")
att_data = ws_att.get_all_records()
attendance_df = pd.DataFrame(att_data)
attendance_df.columns = attendance_df.columns.str.strip()

# ---- Helpers ----
def clean_qai_id(x):
    if pd.isna(x): 
        return None
    x = str(x).upper().strip().replace(" ", "_")
    x = re.sub(r"_+", "_", x)
    return x

def to_num(s):
    return pd.to_numeric(s, errors="coerce")

def normalize_month(value):
    if pd.isna(value):
        return None
    value = str(value).strip().lower()
    months = {
        "jan": "January", "feb": "February", "mar": "March", "apr": "April",
        "may": "May", "jun": "June", "jul": "July", "aug": "August",
        "sep": "September", "oct": "October", "nov": "November", "dec": "December"
    }
    for abbr, full in months.items():
        if value.startswith(abbr):
            return full
    return value.capitalize()

def clean_for_gsheet(df):
    """Clean invalid JSON/float values before upload"""
    return df.replace([np.inf, -np.inf, np.nan], "").fillna("").astype(str)

# ==== 5) Normalize/rename columns ====
pdr_df = pdr_df.rename(columns={
    "Project Batch": "Project name",
    "SUM of Effective Work Hour": "Project Hour"
})

# Attendance sheet: handle Attendance Score or Score
att_colmap = {}
if "QAI_ID" not in attendance_df.columns and "ID" in attendance_df.columns:
    att_colmap["ID"] = "QAI_ID"
attendance_df = attendance_df.rename(columns=att_colmap)

# ---- Attendance numeric handling ----
if "Attendance Score" in attendance_df.columns:
    attendance_df["Attendance Score"] = to_num(attendance_df["Attendance Score"]).fillna(0)
    attendance_df["Score"] = attendance_df["Attendance Score"]  # unify naming
elif "Score" in attendance_df.columns:
    attendance_df["Score"] = to_num(attendance_df["Score"]).fillna(0)
else:
    attendance_df["Score"] = 0

if "Training and assessment performance" in attendance_df.columns:
    attendance_df["Training and assessment performance"] = to_num(
        attendance_df["Training and assessment performance"]
    ).fillna(0)
else:
    attendance_df["Training and assessment performance"] = 0

# ==== 6) Ensure numeric columns in Lead + PDR ====
lead_num_cols = [
    "Quality Score (RCA)",
    "Project Delivery Timeliness",
    "Documentation & Reporting",
    "Communication Efficiency",
    "Discipline & Punctuality",
]

if "Communication Efficiency " in lead_df.columns and "Communication Efficiency" not in lead_df.columns:
    lead_df = lead_df.rename(columns={"Communication Efficiency ": "Communication Efficiency"})

lead_df[lead_num_cols] = lead_df[lead_num_cols].apply(to_num).fillna(0)
pdr_df["Project Hour"] = to_num(pdr_df.get("Project Hour", 0)).fillna(0)
pdr_df["PDR"] = to_num(pdr_df.get("PDR", 0)).fillna(0)

# ==== 7) Clean IDs and Months ====
lead_df["QAI_ID"] = lead_df["QAI_ID"].apply(clean_qai_id)
if "QAI_ID" in attendance_df.columns:
    attendance_df["QAI_ID"] = attendance_df["QAI_ID"].apply(clean_qai_id)

lead_df["Month"] = lead_df["Month"].apply(normalize_month)
attendance_df["Month"] = attendance_df["Month"].apply(normalize_month)

# ==== 8) Monthly KPI Averages ====
monthly_core = (
    lead_df.groupby(["Month", "QAI_ID"], as_index=False)
    .agg({
        "Quality Score (RCA)": "mean",
        "Project Delivery Timeliness": "mean",
        "Documentation & Reporting": "mean",
        "Communication Efficiency": "mean",
        "Discipline & Punctuality": "mean",
        "Lead": "first",
        "Project name": lambda x: ", ".join(sorted(set(pd.Series(x).dropna())))
    })
)

# ==== 8b) Calculate Project Count per Month per QAI_ID ====
project_count = (
    lead_df.groupby(["Month", "QAI_ID"], as_index=False)
    .agg({"Project name": lambda x: len(set(pd.Series(x).dropna()))})
    .rename(columns={"Project name": "Project Count"})
)

# ==== 9–13) Contributions and Attendance Merge ====
lead_with_hours = lead_df.merge(
    pdr_df[["Project name", "PDR", "Project Hour"]],
    on="Project name",
    how="left"
)
lead_with_hours["PDR"] = to_num(lead_with_hours["PDR"]).fillna(0)
lead_with_hours["Project Hour"] = to_num(lead_with_hours["Project Hour"]).fillna(0)
lead_with_hours["Weighted_Contribution"] = lead_with_hours["PDR"] * lead_with_hours["Project Hour"]

lead_contrib = (
    lead_with_hours.groupby(["Month", "QAI_ID"], as_index=False)
    .agg({"Weighted_Contribution": "sum"})
    .rename(columns={"Weighted_Contribution": "Lead_Contribution"})
)
total_contrib = (
    lead_contrib.groupby("Month", as_index=False)
    .agg({"Lead_Contribution": "sum"})
    .rename(columns={"Lead_Contribution": "Total_Month_Contribution"})
)
lead_contrib = lead_contrib.merge(total_contrib, on="Month", how="left")
lead_contrib["Contribution_%"] = (
    (lead_contrib["Lead_Contribution"] / lead_contrib["Total_Month_Contribution"]) * 100
).round(2).fillna(0)

def contribution_to_rating(pct):
    if pct >= 20: return 5
    if pct >= 16: return 4
    if pct >= 11: return 3
    if pct >= 5:  return 2
    return 1

lead_contrib["Contribution_Rating"] = lead_contrib["Contribution_%"].apply(contribution_to_rating)

attendance_agg = (
    attendance_df.groupby(["Month", "QAI_ID"], as_index=False)
    .agg({
        "Score": "mean",
        "Training and assessment performance": "mean"
    })
    .rename(columns={
        "Score": "Attendance",
        "Training and assessment performance": "Training and assessment performance"
    })
)

merged = monthly_core.merge(lead_contrib, on=["Month", "QAI_ID"], how="left")
merged = merged.merge(attendance_agg, on=["Month", "QAI_ID"], how="left")
merged = merged.merge(project_count, on=["Month", "QAI_ID"], how="left")

for c in ["Contribution_%", "Contribution_Rating", "Attendance", "Training and assessment performance"]:
    if c not in merged.columns:
        merged[c] = 0
    merged[c] = to_num(merged[c]).fillna(0)

# ==== 14) Weighted Scoring ====
merged["Score_Quality"]       = 0.20  * merged["Quality Score (RCA)"]
merged["Score_Timeliness"]    = 0.10  * merged["Project Delivery Timeliness"]
merged["Score_Documentation"] = 0.10  * merged["Documentation & Reporting"]
merged["Score_Communication"] = 0.10  * merged["Communication Efficiency"]
merged["Score_Discipline"]    = 0.075 * merged["Discipline & Punctuality"]
merged["Score_Contribution"]  = 0.15  * merged["Contribution_Rating"]
merged["Score_Attendance"]    = 0.075 * merged["Attendance"]
merged["Score_Training"]      = 0.20  * merged["Training and assessment performance"]

merged["Final KPI Score"] = (
    merged["Score_Quality"] +
    merged["Score_Timeliness"] +
    merged["Score_Documentation"] +
    merged["Score_Communication"] +
    merged["Score_Discipline"] +
    merged["Score_Contribution"] +
    merged["Score_Attendance"] +
    merged["Score_Training"]
).round(2)

# ==== 15) Final Report ====
final_report = merged[[
    "Month", "QAI_ID", "Lead", "Project name", "Project Count",
    "Score_Quality", "Score_Timeliness", "Score_Documentation",
    "Score_Communication", "Score_Discipline",
    "Score_Contribution", "Score_Attendance", "Score_Training",
    "Final KPI Score"
]].copy()

final_report.columns = [
    "Month",
    "QAI_ID",
    "Lead",
    "Project Name",
    "Project Count",
    "Quality Score (RCA) (Out of 1.00 | Weight: 20%)",
    "Project Delivery Timeliness (Out of 0.50 | Weight: 10%)",
    "Documentation & Reporting (Out of 0.50 | Weight: 10%)",
    "Communication Efficiency (Out of 0.50 | Weight: 10%)",
    "Discipline & Punctuality (Out of 0.375 | Weight: 7.5%)",
    "Contribution Rating (Out of 0.75 | Weight: 15%)",
    "Attendance (Out of 0.375 | Weight: 7.5%)",
    "Training & Assessment Performance (Out of 1.00 | Weight: 20%)",
    "Final KPI Score (Weighted Total Out of 5.00)"
]

final_report = clean_for_gsheet(final_report)

# ==== 15b) Export Logs to Excel ====
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
log_folder = f"./lead_kpi_logs_{timestamp}"
os.makedirs(log_folder, exist_ok=True)
log_file_path = os.path.join(log_folder, f"lead_kpi_logs_{timestamp}.xlsx")

with ExcelWriter(log_file_path, engine="openpyxl") as writer:
    monthly_core.to_excel(writer, sheet_name="01_Monthly_Core", index=False)
    lead_with_hours.to_excel(writer, sheet_name="02_Lead_With_Hours", index=False)
    lead_contrib.to_excel(writer, sheet_name="03_Lead_Contribution", index=False)
    attendance_agg.to_excel(writer, sheet_name="04_Attendance_Aggregate", index=False)
    merged.to_excel(writer, sheet_name="05_Merged_Before_Scoring", index=False)
    final_report.to_excel(writer, sheet_name="06_Final_Report", index=False)

    scoring_info = pd.DataFrame({
        "Metric": [
            "Quality Score (RCA)",
            "Project Delivery Timeliness",
            "Documentation & Reporting",
            "Communication Efficiency",
            "Discipline & Punctuality",
            "Contribution Rating",
            "Attendance",
            "Training & Assessment Performance",
            "TOTAL"
        ],
        "Weight (%)": [20, 10, 10, 10, 7.5, 15, 7.5, 20, 100],
        "Out of (5 × Weight)": [1.00, 0.50, 0.50, 0.50, 0.375, 0.75, 0.375, 1.00, 5.00]
    })
    scoring_info.to_excel(writer, sheet_name="Scoring_Breakdown", index=False)

print(f"✅ Excel log file created: {log_file_path}")

# ==== 16) Upload to Google Sheets ====
try:
    ws_report = spreadsheet_lead.worksheet("Final Report_Lead")
    spreadsheet_lead.del_worksheet(ws_report)
except:
    pass

ws_report = spreadsheet_lead.add_worksheet(title="Final Report_Lead", rows=2000, cols=30)
ws_report.update([final_report.columns.values.tolist()] + final_report.values.tolist())

print("✅ Successfully exported: Final Report_Lead")
print(f"✅ All detailed logs saved at: {log_folder}")
