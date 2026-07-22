"""
zone_map.py — Modul ringkasan progress Zone & Kolom (Daily & Accumulative Progress)
untuk dashboard S-Curve JK7. Import modul ini ke app.py yang sudah ada.

STRUKTUR SHEET YANG DIPERLUKAN (tab terpisah, nama bebas, default "zone_status"):
    Date       | Level | Metric | Done | Target
    2026-07-20 | GF    | Kolom  | 518  | 522
    2026-07-19 | L1    | Zone   | 88   | 212
    2026-07-20 | L1    | Zone   | 88   | 212
    2026-07-20 | L1    | Kolom  | 269  | 522

- Date   : tanggal snapshot/update (format YYYY-MM-DD)
- Level  : "GF" / "L1" / "L2" dst. Bebas ditulis "Kolom GF", "Level 1", "Lt 1",
           dll -- otomatis dinormalisasi (lihat normalize_level).
- Metric : JENIS hitungan untuk baris itu -- WAJIB diisi salah satu:
           "Zone"  -> hitungan monitoring zone (mis. 24/32 zone)
           "Kolom" -> hitungan kolom individual (mis. 269/522 kolom)
           Ini PENTING: Level yang sama bisa punya progress Zone dan Kolom
           yang berbeda-beda, makanya kolom ini wajib ada supaya tidak tercampur.
- Done   : jumlah yang SUDAH selesai (kumulatif) untuk kombinasi Level+Metric itu
- Target : total target untuk kombinasi Level+Metric itu

CARA PAKAI HARIAN:
    Tiap hari, tambah baris baru per (Level, Metric) dengan angka "Done" terbaru
    (kumulatif). Kalau level itu punya 2 metrik (Zone & Kolom), berarti 2 baris
    per hari untuk level tsb. Dari situ otomatis dihitung:
    - CURRENT   : penambahan dari update sebelumnya ke update terbaru
    - PREVIOUS  : penambahan dari update sebelum-sebelumnya ke update sebelumnya
    - WEEKLY    : penambahan dalam 7 hari terakhir
    - TOTAL / REMAINING / PERCENTAGE : dari baris terbaru
"""

import streamlit as st
import pandas as pd
import os
from datetime import timedelta


def normalize_level(raw: str) -> str:
    """Ubah teks Level apapun (mis. 'Kolom Level 1', 'Zone Level 1', 'Lt 1', 'L1',
    'Kolom GF', 'Ground Floor') jadi salah satu dari 'GF', 'L1', 'L2', dst.
    Kalau tidak dikenali, dikembalikan apa adanya (biar kelihatan di data mentah)."""
    if raw is None:
        return ""
    text = str(raw).strip().lower()
    text = "".join(ch for ch in text if ch.isalnum() or ch.isspace())

    if "gf" in text or "ground" in text:
        return "GF"

    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return f"L{digits}"

    return str(raw).strip()


def normalize_metric(raw: str) -> str:
    """Ubah teks Metric jadi 'Zone' atau 'Kolom'. Default 'Zone' kalau tidak jelas."""
    if raw is None:
        return "Zone"
    text = str(raw).strip().lower()
    if "kolom" in text or "column" in text:
        return "Kolom"
    if "zone" in text:
        return "Zone"
    return str(raw).strip() or "Zone"


@st.cache_data(ttl=30)
def load_zone_progress(_client, sheet_id: str, worksheet_name: str = "zone_status") -> pd.DataFrame:
    ws = _client.open_by_key(sheet_id).worksheet(worksheet_name)
    records = ws.get_all_records()
    df = pd.DataFrame(records)

    # Bersihkan spasi tak terlihat di nama kolom (mis. "Date " -> "Date"),
    # penyebab paling umum error "kolom tidak ditemukan" padahal kelihatan ada di sheet.
    df.columns = [str(c).strip() for c in df.columns]

    required = ["Date", "Level", "Metric", "Done", "Target"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        # PENTING: jangan panggil st.error()/st.stop() di dalam fungsi yang di-cache
        # (@st.cache_data) -- itu bikin Streamlit nyangkut loading terus, bukan
        # berhenti rapi. Lempar exception biasa, baru ditangkap & ditampilkan
        # di luar fungsi cache (lihat app.py).
        raise ValueError(
            f"Kolom wajib tidak ditemukan di sheet '{worksheet_name}': {missing}. "
            f"Kolom yang terbaca: {list(df.columns)}"
        )

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Level"] = df["Level"].apply(normalize_level)
    df["Metric"] = df["Metric"].apply(normalize_metric)
    df["Done"] = pd.to_numeric(df["Done"], errors="coerce").fillna(0)
    df["Target"] = pd.to_numeric(df["Target"], errors="coerce").fillna(0)
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def append_zone_progress(client, sheet_id: str, date_str: str, level: str, metric: str,
                          done: int, target: int, worksheet_name: str = "zone_status"):
    """Tambah baris baru (snapshot hari ini) untuk 1 kombinasi Level+Metric."""
    ws = client.open_by_key(sheet_id).worksheet(worksheet_name)
    ws.append_row([date_str, level, metric, done, target])
    return True, "Progress tersimpan."


def compute_progress_summary(zone_df: pd.DataFrame, level: str, metric: str) -> dict | None:
    """Hitung Daily Progress (previous/current/weekly) & Accumulative Progress
    (total/remaining/percentage) untuk 1 kombinasi Level+Metric."""
    df = zone_df[(zone_df["Level"] == level) & (zone_df["Metric"] == metric)]
    df = df.sort_values("Date").reset_index(drop=True)
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


def render_progress_summary(zone_df: pd.DataFrame, level: str, metric: str,
                             title: str, unit_label: str | None = None,
                             image_path: str | None = None):
    """Render panel ringkasan persis seperti gambar cutoff: Daily Progress & Accumulative Progress,
    untuk 1 kombinasi Level+Metric (mis. Level='L1', Metric='Zone').

    image_path: opsional, path ke gambar denah statis (mis. 'assets/denah_gf.jpeg')
    yang mau ditampilkan di samping/atas ringkasan. Kalau file tidak ada, dilewati
    diam-diam (tidak error)."""
    s = compute_progress_summary(zone_df, level, metric)
    unit_label = unit_label or metric.lower()
    st.markdown(f"##### {title}")

    if s is None:
        st.info(f"Belum ada data untuk {level} - {metric}. Isi lewat form update di bawah.")
        return

    if image_path:
        img_col, info_col = st.columns([1, 1.4])
    else:
        img_col, info_col = None, st.container()

    if image_path and img_col is not None:
        with img_col:
            if os.path.exists(image_path):
                st.image(image_path, use_container_width=True)
            else:
                st.caption(f"(gambar '{image_path}' belum ada di repo)")

    with info_col:
        st.caption(f"CUT OFF {s['last_date'].strftime('%d %B %Y').upper()}")

        trend_icon = "✅" if s["remaining"] <= 0 else "📈"
        st.markdown(
            f"**TOTAL : {s['total']}/{s['target']} {unit_label} "
            f"({s['pct']:.2f}%) {s['current_new']:+d} {trend_icon}**"
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
