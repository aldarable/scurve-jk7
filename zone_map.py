"""
zone_map.py — Modul peta zona & progress checklist (Kolom GF / Zone L1 / Zone L2)
untuk dashboard S-Curve JK7. Import modul ini ke app.py yang sudah ada.

STRUKTUR SHEET BARU YANG DIPERLUKAN (tab terpisah, nama bebas, default "zone_status"):
    Level | ZoneNo | Status     | DateUpdate | X (opsional) | Y (opsional)
    GF    | 33     | Tercor     | 2026-05-14 |              |
    L1    | 65     | Tercor     | 2026-05-22 |              |
    L1    | 82     | Besi       | 2026-05-27 |              |
    L2    | 97     | Belum      |            |              |

- Level      : "GF" / "L1" / "L2" dst
- ZoneNo     : nomor zone (angka), unik per Level
- Status     : salah satu dari "Belum", "Bekisting", "Besi", "Tercor"
               (urutan tahap: Belum -> Bekisting & Scaffolding -> Besi -> Tercor = selesai)
               Untuk GF yang cuma butuh 1 status akhir, cukup pakai "Belum" / "Tercor".
- DateUpdate : tanggal terakhir status berubah (format YYYY-MM-DD), dipakai untuk
               menghitung Daily Progress (previous/current/weekly) di ringkasan.
- X, Y       : opsional, hanya diisi kalau kamu mau overlay titik di atas gambar
               denah asli (lihat render_zone_map). Kalau tidak dipakai, kosongkan saja.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from PIL import Image

STATUS_ORDER = ["Belum", "Bekisting", "Besi", "Tercor"]

STATUS_COLOR = {
    "Tercor": "#6b5bd6",      # ungu - "Sudah Tercor" (selesai)
    "Besi": "#e8c34c",        # kuning - "Terpasang Besi"
    "Bekisting": "#8fd67f",   # hijau - "Terpasang Bekisting & Scaffolding"
    "Belum": "#d9dce1",       # abu - belum mulai
}
STATUS_ICON = {
    "Tercor": "✅",
    "Besi": "📈",
    "Bekisting": "📈",
    "Belum": "⬜",
}

# Kata kunci fleksibel: apapun yang kamu ketik di sheet (Done, Done✅, DONE, Tercor,
# Selesai, dsb) akan dikenali dan dipetakan ke salah satu dari 4 status baku di atas.
# Ini supaya kamu tidak perlu ketik ulang data yang sudah ada di sheet.
STATUS_KEYWORDS = {
    "Tercor": ["done", "tercor", "selesai", "finish", "cor", "complete"],
    "Besi": ["besi", "rebar", "steel"],
    "Bekisting": ["bekisting", "scaffolding", "formwork"],
    "Belum": ["belum", "pending"],
}


def normalize_status(raw: str) -> str:
    """Ubah teks status apapun (mis. 'Done✅', 'done', 'Tercor') jadi salah satu
    dari STATUS_ORDER. Kalau tidak dikenali sama sekali / kosong, dianggap 'Belum'."""
    if raw is None:
        return "Belum"
    text = str(raw).strip().lower()
    # buang emoji/simbol non-huruf supaya "done✅" match dengan "done"
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace()).strip()
    if not text:
        return "Belum"
    for status, keywords in STATUS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return status
    return "Belum"


@st.cache_data(ttl=30)
def load_zone_status(_client, sheet_id: str, worksheet_name: str = "zone_status") -> pd.DataFrame:
    ws = _client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    required = ["Level", "ZoneNo", "Status"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Kolom wajib tidak ditemukan di sheet '{worksheet_name}': {missing}")
        st.stop()

    df["ZoneNo"] = pd.to_numeric(df["ZoneNo"], errors="coerce")
    df["Status"] = df["Status"].apply(normalize_status)

    if "DateUpdate" not in df.columns:
        df["DateUpdate"] = ""
    df["DateUpdate"] = df["DateUpdate"].fillna("").astype(str)

    for c in ("X", "Y"):
        if c not in df.columns:
            df[c] = pd.NA
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def update_zone_status(client, sheet_id: str, zone_no: int, level: str,
                        status: str, date_update: str, worksheet_name: str = "zone_status"):
    """Update status 1 zone di sheet. Dipanggil dari form input di app.py."""
    ws = client.open_by_key(sheet_id).worksheet(worksheet_name)
    header = ws.row_values(1)
    level_col_idx = header.index("Level")
    zone_col_idx = header.index("ZoneNo")

    all_values = ws.get_all_values()
    row_idx = None
    for i, row in enumerate(all_values[1:], start=2):  # skip header
        if len(row) > max(level_col_idx, zone_col_idx):
            if row[level_col_idx] == level and str(row[zone_col_idx]) == str(zone_no):
                row_idx = i
                break

    if row_idx is None:
        return False, "Zone tidak ditemukan (cek Level & ZoneNo)."

    col_status = header.index("Status") + 1
    col_date = header.index("DateUpdate") + 1

    ws.update_cell(row_idx, col_status, status)
    ws.update_cell(row_idx, col_date, date_update)
    return True, "Status zone tersimpan."


def compute_zone_summary(zone_df: pd.DataFrame, level: str) -> dict:
    """Hitung ringkasan Daily Progress & Accumulative Progress, mirip layout gambar cutoff."""
    df = zone_df[zone_df["Level"] == level].copy()
    total = len(df)
    done = int((df["Status"] == "Tercor").sum())
    remaining = total - done
    pct = (done / total * 100) if total else 0.0

    dates = pd.to_datetime(df.loc[df["DateUpdate"] != "", "DateUpdate"], errors="coerce").dropna()
    today = pd.Timestamp(datetime.now().date())
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    current_new = int((dates.dt.date == today.date()).sum())
    previous_new = int((dates.dt.date == yesterday.date()).sum())
    weekly_new = int((dates >= week_ago).sum())

    return {
        "total": total, "done": done, "remaining": remaining, "pct": pct,
        "current_new": current_new, "previous_new": previous_new, "weekly_new": weekly_new,
    }


def render_zone_summary(zone_df: pd.DataFrame, level: str, title: str, short_label: str | None = None):
    """Render blok ringkasan seperti gambar Level 1 / Level 2 (Daily & Accumulative Progress).

    short_label: label singkat buat baris ringkasan, mis. 'Cor Ground Floor' atau
    'Cor Level 1'. Kalau tidak diisi, otomatis pakai 'Cor {level}'.
    """
    s = compute_zone_summary(zone_df, level)
    icon = " ✅" if s["total"] > 0 and s["done"] == s["total"] else " 📈"
    label = short_label or f"Cor {level}"
    st.markdown(f"#### {title}")
    st.markdown(f"**{label} ({s['done']}/{s['total']}){icon}**")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**DAILY PROGRESS**")
        st.write(f"PREVIOUS : {s['previous_new']} Zone")
        st.write(f"CURRENT  : {s['current_new']} Zone")
        st.write(f"WEEKLY (7 days) : {s['weekly_new']} Zone")
    with c2:
        st.markdown("**ACCUMULATIVE PROGRESS**")
        st.write(f"TOTAL      : {s['done']}/{s['total']} Zone")
        st.write(f"REMAINING  : {s['remaining']} Zone")
        st.write(f"PERCENTAGE : {s['pct']:.2f}%")


def render_zone_map(zone_df: pd.DataFrame, level: str, bg_image_path: str | None = None):
    """Opsional: render titik zone di atas gambar denah asli (butuh kolom X,Y terisi)."""
    df = zone_df[zone_df["Level"] == level].dropna(subset=["X", "Y"]).copy()
    if df.empty:
        st.info("Kolom X,Y belum diisi untuk level ini — peta visual dilewati, "
                 "checklist di bawah tetap jalan seperti biasa.")
        return

    fig = go.Figure()
    if bg_image_path:
        img = Image.open(bg_image_path)
        fig.add_layout_image(dict(
            source=img, xref="x", yref="y",
            x=0, y=img.height, sizex=img.width, sizey=img.height,
            sizing="stretch", layer="below",
        ))
        fig.update_xaxes(range=[0, img.width], visible=False)
        fig.update_yaxes(range=[0, img.height], visible=False, scaleanchor="x")
    else:
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False, autorange="reversed")

    for status in STATUS_ORDER:
        sub = df[df["Status"] == status]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["X"], y=sub["Y"], mode="markers+text",
            marker=dict(size=16, color=STATUS_COLOR[status], line=dict(color="#14181d", width=1)),
            text=sub["ZoneNo"].astype(int).astype(str),
            textposition="middle center", textfont=dict(size=8, color="#14181d"),
            name=f"{status} ({len(sub)})",
            hovertext=sub.apply(
                lambda r: f"Zone {int(r['ZoneNo'])} — {r['Status']}"
                          + (f" ({r['DateUpdate']})" if r["DateUpdate"] else ""), axis=1),
            hoverinfo="text",
        ))

    fig.update_layout(
        height=600, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_zone_checklist(zone_df: pd.DataFrame, level: str, n_cols: int = 2):
    """Render daftar checklist zone, mis. 'Zone 33 (14/5) checkmark', dalam beberapa kolom."""
    df = zone_df[zone_df["Level"] == level].sort_values("ZoneNo")
    cols = st.columns(n_cols)
    per_col = -(-len(df) // n_cols)  # ceil division
    for i, col in enumerate(cols):
        chunk = df.iloc[i * per_col:(i + 1) * per_col]
        lines = []
        for _, r in chunk.iterrows():
            icon = STATUS_ICON.get(r["Status"], "⬜")
            date_str = ""
            if r["DateUpdate"]:
                try:
                    d = pd.to_datetime(r["DateUpdate"])
                    date_str = f" ({d.day}/{d.month})"
                except Exception:
                    date_str = f" ({r['DateUpdate']})"
            lines.append(f"{int(r['ZoneNo'])}. Zone {int(r['ZoneNo'])}{date_str} {icon}")
        col.markdown("  \n".join(lines))
