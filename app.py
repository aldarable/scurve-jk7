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

st.set_page_config(
    page_title="S-Curve Structure - JK7",
    page_icon="📈",
    layout="wide",
)

WORKSHEET_NAME = "initial_data_for_gsheet" 
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
            f"Kolom wajib tidak ditemukan di sheet: {missing}. "
            f"Cek header baris 1 di Google Sheet kamu."
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
    """Hitung kolom kumulatif & deviasi dari data mentah (PlanZoning/ActualZoning)."""
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
    """Update baris ActualZoning & Remarks di Google Sheet untuk tanggal tertentu."""
    ws = get_worksheet()
    dates = ws.col_values(1) 
    try:
        row_idx = dates.index(target_date) + 1 
    except ValueError:
        return False, "Tanggal tidak ditemukan di sheet. Pastikan formatnya YYYY-MM-DD."

    header = ws.row_values(1)
    col_actual = header.index("ActualZoning") + 1
    col_remarks = header.index("Remarks") + 1

    ws.update_cell(row_idx, col_actual, qty)
    if remarks:
        ws.update_cell(row_idx, col_remarks, remarks)
    return True, "Tersimpan."


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
    st.caption(f"Update terakhir: {last_row['Date'].strftime('%d %B %Y')}")


# ACCUMULATION
c1, c2, c3, c4 = st.columns(4)
c1.metric("Plan Progress", f"{plan_today:.1f}%")
c2.metric("Actual Progress", f"{actual_today:.1f}%")
c3.metric("Deviasi", f"{deviation:+.1f}%")
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
    height=420, yaxis_title="% Kumulatif", yaxis_range=[0, 100],
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    margin=dict(l=10, r=10, t=10, b=10),
)
st.plotly_chart(fig_s, use_container_width=True)


# S-Curve Progress (Deviation)
st.subheader("📉 S-Curve Deviation")

def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Konversi warna hex (#rrggbb) ke string rgba() yang valid untuk Plotly."""
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
    height=220, yaxis_title="% poin",
    margin=dict(l=10, r=10, t=10, b=10), showlegend=False,
)
st.plotly_chart(fig_dev, use_container_width=True)
st.caption("Di atas 0 = lebih cepat dari plan · di bawah 0 = tertinggal dari plan")

st.divider()


# INPUT FORM & MILESTONE LIST
col_form, col_milestone = st.columns([1.1, 1])

with col_form:
    st.subheader("Input Update Harian")
    with st.form("update_form", clear_on_submit=True):
        date_input = st.date_input("Tanggal", value=next_date)
        qty_input = st.number_input("Zoning Aktual (unit)", min_value=0.0, step=1.0)
        remarks_input = st.text_input("Remarks / Milestone (opsional)")
        submitted = st.form_submit_button("Simpan Update", type="primary")

        if submitted:
            ok, msg = update_actual(date_input.strftime("%Y-%m-%d"), qty_input, remarks_input)
            if ok:
                st.cache_data.clear()
                st.success("Update tersimpan ke Google Sheet ✅")
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


# TABEL DATA TERBARU
st.subheader("Data Terbaru")
window_start = max(0, (last_actual_idx or 0) - 6)
window_end = (last_actual_idx or 0) + 8
table_df = df.iloc[window_start:window_end][
    ["Date", "PlanZoning", "PlanPct", "ActualZoning", "ActualPct", "Dev", "Remarks"]
].copy()
table_df.columns = ["Tanggal", "Plan/hari", "Plan Kum%", "Actual/hari", "Actual Kum%", "Deviasi", "Remarks"]
for col in ["Plan Kum%", "Actual Kum%", "Deviasi"]:
    table_df[col] = table_df[col].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "-")
st.dataframe(table_df, hide_index=True, use_container_width=True)
