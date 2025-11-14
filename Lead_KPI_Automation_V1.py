# ============================================================
# Lead KPI Automation Script
# Reads Lead & Project Hours sheets, calculates KPIs, exports to Report Sheet
# ============================================================

import pandas as pd
import numpy as np
import re
import gspread
from google.oauth2.service_account import Credentials
import os

# ==== 1) Read environment variables ====
SHEET_ID_LEAD = os.getenv("SHEET_ID_LEAD")
SHEET_ID_PDR = os.getenv("SHEET_ID_PDR")
SHEET_ID_REPORT = os.getenv("SHEET_ID_REPORT")

if not SHEET_ID_LEAD or not SHEET_ID_PDR or not SHEET_ID_REPORT:
    raise ValueError("Missing required Sheet IDs in environment variables.")

# ==== 2) Connect to Google Sheets using service account JSON ====
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
client = gspread.authorize(creds)

# ==== 3) Load Sheets ====
spreadsheet_lead = client.open_by_key(SHEET_ID_LEAD)
spreadsheet_pdr = client.open_by_key(SHEET_ID_PDR)
spreadsheet_report = client.open_by_key(SHEET_ID_REPORT)

# Lead Sheet
ws_lead = spreadsheet_lead.worksheet("Lead")
lead_data = ws_lead.get("B:J")
lead_df = pd.DataFrame(lead_data[1:], columns=lead_data[0])
lead_df.columns = lead_df.columns.str.strip()

# Attendance Sheet
ws_att = spreadsheet_lead.worksheet("Attendance")
att_data = ws_att.get_all_records()
attendance_df = pd.DataFrame(att_data)
attendance_df.columns = attendance_df.columns.str.strip()

# Project Hours Sheet
ws_pdr = spreadsheet_pdr.worksheet("Project_Hours")
pdr_data = ws_pdr.get_all_records()
pdr_df = pd.DataFrame(pdr_data)
pdr_df.columns = pdr_df.columns.str.strip()

# ==== 4) Helper Functions ====
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

# ==== 5) Clean & Normalize Data ====
pdr_df = pdr_df.rename(columns={
    "Project Batch": "Project name",
    "SUM of Effective Work Hour": "Project Hour"
})

if "QAI_ID" not in attendance_df.columns and "ID" in attendance_df.columns:
    attendance_df = attendance_df.rename(columns={"ID": "QAI_ID"})

# Attendance numeric
if "Attendance Score" in attendance_df.columns:
    attendance_df["Score"] = to_num(attendance_df["Attendance Score"]).fillna(0)
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

lead_df["QAI_ID"] = lead_df["QAI_ID"].apply(clean_qai_id)
attendance_df["QAI_ID"] = attendance_df["QAI_ID"].apply(clean_qai_id)

lead_df["Month"] = lead_df["Month"].apply(normalize_month)
attendance_df["Month"] = attendance_df["Month"].apply(normalize_month)

lead_num_cols = [
    "Quality Score (RCA)",
    "Project Delivery Timeliness",
    "Documentation & Reporting",
    "Communication Efficiency",
    "Discipline & Punctuality",
]

lead_df[lead_num_cols] = lead_df[lead_num_cols].apply(to_num).fillna(0)
pdr_df["Project Hour"] = to_num(pdr_df.get("Project Hour", 0)).fillna(0)
pdr_df["PDR"] = to_num(pdr_df.get("PDR", 0)).fillna(0)

# ==== 6) Monthly Core Metrics ====
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

# ==== 7) Project Count ====
project_count = (
    lead_df.groupby(["Month", "QAI_ID"], as_index=False)
    .agg({"Project name": lambda x: len(set(pd.Series(x).dropna()))})
    .rename(columns={"Project name": "Project Count"})
)

# ==== 8) Contributions ====
lead_with_hours = lead_df.merge(
    pdr_df[["Project name", "PDR", "Project Hour"]],
    on="Project name",
    how="left"
)

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
    lead_contrib["Lead_Contribution"] / lead_contrib["Total_Month_Contribution"] * 100
).round(2).fillna(0)

def contribution_to_rating(pct):
    if pct >= 20: return 5
    if pct >= 16: return 4
    if pct >= 11: return 3
    if pct >= 5:  return 2
    return 1

lead_contrib["Contribution_Rating"] = lead_contrib["Contribution_%"].apply(contribution_to_rating)

# ==== 9) Attendance Aggregate ====
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

# ==== 10) Merge All Data ====
merged = monthly_core.merge(lead_contrib, on=["Month", "QAI_ID"], how="left")
merged = merged.merge(attendance_agg, on=["Month", "QAI_ID"], how="left")
merged = merged.merge(project_count, on=["Month", "QAI_ID"], how="left")

for c in ["Contribution_%", "Contribution_Rating", "Attendance", "Training and assessment performance"]:
    if c not in merged.columns:
        merged[c] = 0
    merged[c] = to_num(merged[c]).fillna(0)

# ==== 11) Weighted KPI Scoring ====
merged["Score_Quality"]       = 0.20  * merged["Quality Score (RCA)"]
merged["Score_Timeliness"]    = 0.10  * merged["Project Delivery Timeliness"]
merged["Score_Documentation"] = 0.10  * merged["Documentation & Reporting"]
merged["Score_Communication"] = 0.10  * merged["Communication Efficiency"]
merged["Score_Discipline"]    = 0.075 * merged["Discipline & Punctuality"]
merged["Score_Contribution"]  = 0.15  * merged["Contribution_Rating"]
merged["Score_Attendance"]    = 0.075 * merged["Attendance"]
merged["Score_Training"]      = 0.20  * merged["Training and assessment performance"]

merged["Final KPI Score"] = (
    merged["Score_Quality"]
    + merged["Score_Timeliness"]
    + merged["Score_Documentation"]
    + merged["Score_Communication"]
    + merged["Score_Discipline"]
    + merged["Score_Contribution"]
    + merged["Score_Attendance"]
    + merged["Score_Training"]
).round(2)

# ==== 12) Final Report ====
final_report = merged.copy()

# ==== 13) Upload All Tabs to Report Sheet ====
sheet_data = {
    "01_Monthly_Core": monthly_core,
    "02_Lead_With_Hours": lead_with_hours,
    "03_Lead_Contribution": lead_contrib,
    "04_Attendance_Aggregate": attendance_agg,
    "05_Merged_Before_Scoring": merged,
    "06_Final_Report": final_report
}

for sheet_name, df in sheet_data.items():
    try:
        ws = spreadsheet_report.worksheet(sheet_name)
        spreadsheet_report.del_worksheet(ws)
    except gspread.exceptions.WorksheetNotFound:
        pass
    ws_new = spreadsheet_report.add_worksheet(title=sheet_name, rows=len(df)+50, cols=len(df.columns)+5)
    df = df.replace([np.inf, -np.inf, np.nan], "").fillna("")
    ws_new.update([df.columns.values.tolist()] + df.values.tolist())

    print(f"✅ Uploaded tab: {sheet_name} to Report Sheet")
