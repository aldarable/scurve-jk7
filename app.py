"""
S-Curve Dashboard — JK7 Structure Works
"""

import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go
from datetime import datetime, timedelta

from zone_map import (
    load_zone_status, update_zone_status,
    render_zone_summary, render_zone_map, render_zone_checklist,
)

st.set_page_config(
    page_title="S-Curve Structure - JK7",
    page_icon="📈",
    layout="wide",
)

WORKSHEET_NAME = "JK7-Sumaraja-Scurve"


# Connect to GSheets
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def get_worksheet():
    client = get_gspread_client()
    sheet_id = st.secrets["sheet_id"]
    spreadsheet = client.open_by_key(sheet_id)
    return spreadsheet.get_worksheet(0)


RAW_COLUMNS = ["Date", "PlanZoning", "ActualZoning", "Remarks"]


@st.cache_data(ttl=30)
def load_data():
    ws = get_worksheet()
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        st.error(
            f"The following required columns are missing from the sheet: {missing}. "
            f"Please verify that the header row (Row 1) in your Google Sheet contains all required column names."
        )
        st.stop()

    df = df[RAW_COLUMNS].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["PlanZoning"] = pd.to_numeric(df["PlanZoning"], errors="coerce").fillna(0)
    df["ActualZoning"] = pd.to_numeric(
        df["ActualZoning"].replace("", pd.NA), errors="coerce"
    )
    df["Remarks"] = df["Remarks"].fillna("").astype(str)
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cumulative progress and deviation from the raw PlanZoning and ActualZoning data."""
    df = df.copy()
    total_target = df["PlanZoning"].sum()

    df["PlanCum"] = df["PlanZoning"].cumsum()
    df["PlanPct"] = df["PlanCum"] / total_target * 100

    # Actual Cummulative
    has_actual = df["ActualZoning"].notna()
    actual_filled = df["ActualZoning"].fillna(0)
    df["ActualCum"] = actual_filled.cumsum()
    df.loc[~has_actual, "ActualCum"] = np.nan
    # If no other Actual Cumm, will be NaN
    last_actual_idx = df[has_actual].index.max() if has_actual.any() else None
    if last_actual_idx is not None:
        df.loc[df.index > last_actual_idx, "ActualCum"] = np.nan

    df["ActualPct"] = df["ActualCum"] / total_target * 100
    df["Dev"] = df["ActualPct"] - df["PlanPct"]

    return df, total_target, last_actual_idx


def update_actual(target_date: str, qty: float, remarks: str):
    """Update ActualZoning & Remarks in Google Sheets for certain date."""
    ws = get_worksheet()
    dates = ws.col_values(1)
    try:
        row_idx = dates.index(target_date) + 1
    except ValueError:
        return False, "The specified date was not found in the sheet. Please ensure the date is in YYYY-MM-DD format."

    header = ws.row_values(1)
    col_actual = header.index("ActualZoning") + 1
    col_remarks = header.index("Remarks") + 1

    ws.update_cell(row_idx, col_actual, qty)
    if remarks:
        ws.update_cell(row_idx, col_remarks, remarks)
    return True, "Successfully updated ✅."


# PROCESSING DATA
raw_df = load_data()
df, total_target, last_actual_idx = compute_derived(raw_df)

last_row = df.loc[last_actual_idx] if last_actual_idx is not None else None
plan_today = last_row["PlanPct"] if last_row is not None else 0
actual_today = last_row["ActualPct"] if last_row is not None else 0
deviation = (actual_today or 0) - (plan_today or 0)

if deviation >= 0:
    status_label, status_color = "ON TRACK / AHEAD", "#7fd6a0"
elif deviation >= -10:
    status_label, status_color = "SLIGHTLY BEHIND", "#f2c26b"
else:
    status_label, status_color = "BEHIND SCHEDULE", "#f2836b"

next_date = (
    (last_row["Date"] + timedelta(days=1)).date()
    if last_row is not None
    else df["Date"].min().date()
)


# HEADER
st.markdown("##### JK7 STRUCTURE WORKS")
st.title("📊 Construction Progress Dashboard")

if last_row is not None:
    st.caption(f"Last Update: {last_row['Date'].strftime('%d %B %Y')}")


# ACCUMULATION
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plan Progress", f"{plan_today:.1f}%")
c2.metric("Actual Progress", f"{actual_today:.1f}%")
c3.metric("Deviation", f"{deviation:+.1f}%")
with c4:
    st.markdown(
        f"""
        <div style="border:1px solid {status_color}55;background:{status_color}22;
        border-radius:8px;padding:10px 14px;">
        <div style="font-size:12px;color:#888;">STATUS</div>
        <div style="font-size:16px;font-weight:700;color:{status_color};">{status_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()


# S-Curve Progress (Plan vs Actual)
st.subheader("📈 S-Curve Progress (Plan vs Actual)")

fig_s = go.Figure()
fig_s.add_trace(go.Scatter(
    x=df["Date"], y=df["PlanPct"], name="Plan",
    line=dict(color="#5b8ba0", width=2),
))
fig_s.add_trace(go.Scatter(
    x=df["Date"], y=df["ActualPct"], name="Actual",
    line=dict(color="#e8a84c", width=3),
    fill="tozeroy", fillcolor="rgba(232,168,76,0.12)",
))

milestones = df[df["Remarks"] != ""]
fig_s.add_trace(go.Scatter(
    x=milestones["Date"], y=milestones["ActualPct"],
    mode="markers", name="Milestone",
    marker=dict(color="#f2836b", size=8, line=dict(color="#14181d", width=1)),
    text=milestones["Remarks"], hovertemplate="%{text}<extra></extra>",
))

if last_row is not None:
    fig_s.add_vline(x=last_row["Date"], line_dash="dash", line_color="gray", opacity=0.5)

fig_s.update_layout(
    height=420,
    yaxis=dict(title="% Kumulatif", range=[0, 100], ticksuffix="%"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=10, r=10, t=10, b=10),
    hovermode="x unified",
)
fig_s.update_traces(hovertemplate="%{y:.1f}%<extra></extra>", selector=dict(type="scatter"))
st.plotly_chart(fig_s, use_container_width=True)


# S-Curve Progress (Deviation)
st.subheader("📉 S-Curve Deviation")


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert a hex color (#RRGGBB) to a valid RGBA string for Plotly."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


dev_color = "#7fd6a0" if deviation >= 0 else "#f2836b"
fig_dev = go.Figure()
fig_dev.add_trace(go.Scatter(
    x=df["Date"], y=df["Dev"], name="Deviasi",
    line=dict(color=dev_color, width=2),
    fill="tozeroy", fillcolor=hex_to_rgba(dev_color, 0.2),
))
fig_dev.add_hline(y=0, line_color="gray", line_width=1)
if last_row is not None:
    fig_dev.add_vline(x=last_row["Date"], line_dash="dash", line_color="gray", opacity=0.5)

fig_dev.update_layout(
    height=220,
    yaxis=dict(title="% poin", ticksuffix="%"),
    margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
)
fig_dev.update_traces(hovertemplate="%{y:+.1f}%<extra></extra>")
st.plotly_chart(fig_dev, use_container_width=True)
st.caption("Above 0 = Ahead of Schedule • Below 0 = Behind Schedule")

st.divider()


# INPUT & MILESTONE FORM
col_form, col_milestone = st.columns([1.1, 1])

with col_form:
    st.subheader("Daily Report")
    with st.form("update_form", clear_on_submit=True):
        date_input = st.date_input("Date", value=next_date)
        qty_input = st.number_input("Actual Zoning", min_value=0.0, step=1.0)
        remarks_input = st.text_input("Remarks / Milestone (opsional)")
        submitted = st.form_submit_button("Successfully updated ✅", type="primary")

        if submitted:
            ok, msg = update_actual(date_input.strftime("%Y-%m-%d"), qty_input, remarks_input)
            if ok:
                st.cache_data.clear()
                st.success("Successfully updated Google Sheets ✅")
                st.rerun()
            else:
                st.error(msg)

with col_milestone:
    st.subheader(f"Milestone Tracker ({len(milestones)})")
    st.dataframe(
        milestones[["Date", "Remarks"]].rename(columns={"Date": "Tanggal"}),
        hide_index=True, use_container_width=True, height=280,
    )

st.divider()


# NEW DATA
st.subheader("Latest Data")
window_start = max(0, (last_actual_idx or 0) - 6)
window_end = (last_actual_idx or 0) + 8
table_df = df.iloc[window_start:window_end][
    ["Date", "PlanZoning", "PlanPct", "ActualZoning", "ActualPct", "Dev", "Remarks"]
].copy()
table_df.columns = ["Tanggal", "Plan/hari", "Plan Kum%", "Actual/hari", "Actual Kum%", "Deviasi", "Remarks"]
for col in ["Plan Kum%", "Actual Kum%", "Deviasi"]:
    table_df[col] = table_df[col].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
st.dataframe(table_df, hide_index=True, use_container_width=True)


# =========================================================
# ZONE / KOLOM TRACKING (Kolom GF, Zone Level 1, Zone Level 2)
# =========================================================
st.divider()
st.header("🏗️ Zone / Kolom Tracking")
st.caption(
    "Data di bawah ini diambil dari tab 'zone_status' di Google Sheet yang sama. "
    "Update status lewat form di bagian paling bawah, atau edit langsung di sheet."
)

zone_df = load_zone_status(get_gspread_client(), st.secrets["sheet_id"], "zone_status")

tab_gf, tab_l1, tab_l2 = st.tabs(["Kolom GF", "Zone Level 1", "Zone Level 2"])

with tab_gf:
    render_zone_summary(zone_df, "GF", "JK7 STRUCTURE (Kolom GF)", short_label="Cor Ground Floor")
    render_zone_map(zone_df, "GF", bg_image_path="assets/denah_gf.png")  # opsional, lewati jika belum ada
    render_zone_checklist(zone_df, "GF")

with tab_l1:
    render_zone_summary(zone_df, "L1", "JK7 STRUCTURE (Level 1)", short_label="Cor Level 1")
    render_zone_map(zone_df, "L1", bg_image_path="assets/denah_L1.png")  # opsional
    render_zone_checklist(zone_df, "L1")
    
with tab_cgf:
    render_zone_summary(zone_df, "CGF", "JK7 STRUCTURE Kolom (Level GF)", short_label="Kolom Level GF")
    render_zone_map(zone_df, "CGF", bg_image_path="assets/denah_kolom_gf.png")  # opsional
    render_zone_checklist(zone_df, "CGF")

with tab_cl1:
    render_zone_summary(zone_df, "CL1", "JK7 STRUCTURE Kolom (Level 1)", short_label="Kolom Level L1")
    render_zone_map(zone_df, "CL1", bg_image_path="assets/denah_kolom_L1.png")  # opsional
    render_zone_checklist(zone_df, "CL1")
    
with tab_l2:
    render_zone_summary(zone_df, "L2", "JK7 STRUCTURE (Level 2)", short_label="Cor Level 2")
    render_zone_map(zone_df, "L2", bg_image_path="assets/denah_l2.png")  # opsional
    render_zone_checklist(zone_df, "L2")
    
with tab_Cl2:
    render_zone_summary(zone_df, "CL2", "JK7 STRUCTURE Kolom (Level 2)", short_label="Kolom Level 2")
    render_zone_map(zone_df, "CL2", bg_image_path="assets/denah_l2.png")  # opsional
    render_zone_checklist(zone_df, "CL2")

st.divider()

with st.expander("✏️ Update Status Zone/Kolom"):
    with st.form("update_zone_form", clear_on_submit=True):
        level_input = st.selectbox("Level", ["GF", "CGF", "L1", "CL1", "L2"])
        zone_input = st.number_input("Zone / Kolom No.", min_value=1, step=1)
        status_input = st.selectbox("Status", ["Belum", "Bekisting", "Besi", "Tercor"])
        date_zone_input = st.date_input("Tanggal Update", value=datetime.now().date())
        submitted_zone = st.form_submit_button("Simpan Status", type="primary")

        if submitted_zone:
            ok, msg = update_zone_status(
                get_gspread_client(), st.secrets["sheet_id"],
                zone_input, level_input, status_input,
                date_zone_input.strftime("%Y-%m-%d"),
            )
            st.cache_data.clear()
            st.success(msg) if ok else st.error(msg)
            st.rerun()
