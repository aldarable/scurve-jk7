"""
zone_map.py — Modul ringkasan progress Zone/Kolom (Daily & Accumulative Progress)
untuk dashboard S-Curve JK7. Import modul ini ke app.py yang sudah ada.

STRUKTUR SHEET BARU YANG DIPERLUKAN (tab terpisah, nama bebas, default "zone_progress"):
    Date       | Level | Done | Target
    2026-07-19 | GF    | 518  | 522
    2026-07-20 | GF    | 518  | 522
    2026-07-19 | L1    | 88   | 212
    2026-07-20 | L1    | 88   | 212

- Date   : tanggal snapshot/update (format YYYY-MM-DD)
- Level  : "GF" / "L1" / "L2" dst — sesuai level yang kamu punya
- Done   : jumlah zone/kolom yang SUDAH selesai (kumulatif) per tanggal itu
- Target : total zone/kolom yang harus dicapai untuk level itu (biasanya konstan,
           tapi diketik ulang tiap baris supaya fleksibel kalau target berubah)

CARA PAKAI HARIAN:
    Tiap hari, tambah 1 baris baru per level dengan angka "Done" terbaru (kumulatif,
    bukan tambahan hari itu saja). Dari situ modul ini otomatis hitung:
    - CURRENT   : penambahan dari update sebelumnya ke update terbaru
    - PREVIOUS  : penambahan dari update sebelum-sebelumnya ke update sebelumnya
    - WEEKLY    : penambahan dalam 7 hari terakhir
    - TOTAL / REMAINING / PERCENTAGE : dari baris terbaru
"""

import streamlit as st
import pandas as pd
from datetime import timedelta


@st.cache_data(ttl=30)
def load_zone_progress(_client, sheet_id: str, worksheet_name: str = "zone_progress") -> pd.DataFrame:
    ws = _client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    required = ["Date", "Level", "Done", "Target"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Kolom wajib tidak ditemukan di sheet '{worksheet_name}': {missing}")
        st.stop()

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Done"] = pd.to_numeric(df["Done"], errors="coerce").fillna(0)
    df["Target"] = pd.to_numeric(df["Target"], errors="coerce").fillna(0)
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def append_zone_progress(client, sheet_id: str, date_str: str, level: str,
                          done: int, target: int, worksheet_name: str = "zone_progress"):
    """Tambah baris baru (snapshot hari ini) untuk 1 level. Dipanggil dari form di app.py."""
    ws = client.open_by_key(sheet_id).worksheet(worksheet_name)
    ws.append_row([date_str, level, done, target])
    return True, "Progress tersimpan."


def compute_progress_summary(zone_df: pd.DataFrame, level: str) -> dict | None:
    """Hitung Daily Progress (previous/current/weekly) & Accumulative Progress
    (total/remaining/percentage) dari log kumulatif per level."""
    df = zone_df[zone_df["Level"] == level].sort_values("Date").reset_index(drop=True)
    if df.empty:
        return None

    last = df.iloc[-1]
    total = int(last["Done"])
    target = int(last["Target"])
    remaining = target - total
    pct = (total / target * 100) if target else 0.0

    current_new = 0
    previous_new = 0
    if len(df) >= 2:
        current_new = int(df.iloc[-1]["Done"] - df.iloc[-2]["Done"])
    if len(df) >= 3:
        previous_new = int(df.iloc[-2]["Done"] - df.iloc[-3]["Done"])

    week_ago = last["Date"] - timedelta(days=7)
    older = df[df["Date"] <= week_ago]
    if not older.empty:
        weekly_new = int(last["Done"] - older.iloc[-1]["Done"])
    else:
        weekly_new = int(last["Done"] - df.iloc[0]["Done"])

    return {
        "last_date": last["Date"], "total": total, "target": target,
        "remaining": remaining, "pct": pct,
        "current_new": current_new, "previous_new": previous_new, "weekly_new": weekly_new,
    }


def render_progress_summary(zone_df: pd.DataFrame, level: str, title: str, unit_label: str = "Zone"):
    """Render panel ringkasan persis seperti gambar cutoff: Daily Progress & Accumulative Progress."""
    s = compute_progress_summary(zone_df, level)
    st.markdown(f"#### {title}")

    if s is None:
        st.info(f"Belum ada data untuk level {level}. Isi lewat form update di bawah.")
        return

    st.caption(f"CUT OFF {s['last_date'].strftime('%d %B %Y').upper()}")

    # Baris ringkas gabungan, mis. "TOTAL : 518/522 kolom (99.23%) +0"
    trend_icon = "✅" if s["remaining"] <= 0 else "📈"
    st.markdown(
        f"### TOTAL : {s['total']}/{s['target']} {unit_label} "
        f"({s['pct']:.2f}%) {s['current_new']:+d} {trend_icon}"
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**DAILY PROGRESS**")
        st.write(f"PREVIOUS : {s['previous_new']:+d} {unit_label}")
        st.write(f"CURRENT  : {s['current_new']:+d} {unit_label}")
        st.write(f"WEEKLY (7 days) : {s['weekly_new']:+d} {unit_label}")
    with c2:
        st.markdown("**ACCUMULATIVE PROGRESS**")
        st.write(f"TOTAL      : {s['total']}/{s['target']} {unit_label}")
        st.write(f"REMAINING  : {s['remaining']} {unit_label}")
        st.write(f"PERCENTAGE : {s['pct']:.2f}%")
