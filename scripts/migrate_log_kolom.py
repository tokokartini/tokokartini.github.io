# -*- coding: utf-8 -*-
"""Tata ulang kolom tab 'Log': 8 kolom lama -> 9 kolom baru.

Lama: Waktu Staff Rak Produk Satuan SKU Qty ED
Baru: Waktu Staff Rak Produk Rincian Qty Satuan ED SKU

Kolom Rincian dikosongkan untuk baris lama -- riwayat sebelum perubahan ini
memang tidak menyimpan satuan asli yang diketik petugas.

Pakai:
  python migrate_log_kolom.py            # dry-run, cuma laporan
  python migrate_log_kolom.py --tulis    # backup tab Log lalu tulis ulang

Tab output tidak disentuh; formula-nya diperbarui terpisah oleh
setup_sheet.py dan add_arsip_bulanan.py. Rekap!G1 juga tidak disentuh.
"""
import sys
import time
import warnings
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"
TAB = "Log"
# HEADER_LAMA adalah referensi dokumentasi. Live sheet carries "rack" (lowercase) di
# kolom C dari setup sebelumnya; guard akan match case-insensitively.
HEADER_LAMA = ["Waktu", "Staff", "Rak", "Produk", "Satuan", "SKU", "Qty", "ED"]
HEADER_BARU = ["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"]


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(delay)


def headers_match(header, expected_header, length):
    """Bandingkan header case-insensitively, terima kolom C sebagai "rak" atau "rack"."""
    header = (header if header else [])[:length]
    expected = expected_header[:length]

    if len(header) != len(expected):
        return False

    for i, (h, e) in enumerate(zip(header, expected)):
        h_norm = str(h).strip().lower()
        e_norm = str(e).strip().lower()
        # Kolom C (index 2): terima "rak" atau "rack"
        if i == 2:
            if h_norm not in ("rak", "rack") or e_norm not in ("rak", "rack"):
                return False
        else:
            if h_norm != e_norm:
                return False

    return True


def pindah(values):
    """values = get_all_values() termasuk header. Balikkan (baris_baru, jumlah)."""
    rows = []
    for raw in values[1:]:
        row = list(raw) + [""] * (8 - len(raw))
        waktu, staff, rack, produk, satuan, sku, qty, ed = row[:8]
        if not str(produk).strip():
            continue
        rows.append([waktu, staff, rack, produk, "", qty, satuan, ed, sku])
    return rows


def main():
    tulis = "--tulis" in sys.argv

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))
    ws = retry(lambda: sh.worksheet(TAB))
    if ws.col_count < 9:
        retry(lambda: ws.resize(rows=ws.row_count, cols=9))

    values = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))

    # Penjaga: kalau header sudah 9 kolom, migrasi pernah jalan. Menjalankannya
    # dua kali akan menggeser kolom untuk kedua kalinya dan merusak datanya.
    header = (values[0] if values else [])
    if headers_match(header, HEADER_BARU, 9):
        print("BATAL: header Log sudah susunan baru, migrasi tidak perlu diulang.")
        return

    if not headers_match(header, HEADER_LAMA, 8):
        print(f"BATAL: header Log tak dikenali: {header}")
        return

    rows = pindah(values)
    print(f"Log: {len(values) - 1} baris -> {len(rows)} baris")
    print("\ncontoh 5 baris hasil:")
    for r in rows[:5]:
        print("  " + " | ".join(str(x) for x in r))

    if not tulis:
        print("\nDRY-RUN. Tidak ada yang ditulis. Jalankan lagi dengan --tulis untuk menulis.")
        return

    backup_name = f"Log backup kolom {date.today().isoformat()}"
    existing = [w.title for w in retry(lambda: sh.worksheets())]
    if backup_name in existing:
        print(f"BATAL: tab '{backup_name}' sudah ada. Hapus atau ganti nama dulu.")
        return
    retry(lambda: sh.duplicate_sheet(source_sheet_id=ws.id, new_sheet_name=backup_name))
    print(f"backup dibuat: '{backup_name}'")

    # Penjaga tabrakan: kalau ada upload masuk antara pembacaan dan penulisan,
    # baris itu akan tertimpa -- batalkan dan minta dijalankan ulang.
    cek = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))
    if cek != values:
        print("BATAL: Log berubah saat script jalan (ada upload masuk). Jalankan ulang.")
        return

    retry(lambda: ws.batch_clear([f"A1:I{max(len(values), len(rows) + 1) + 10}"]))
    retry(lambda: ws.update(values=[HEADER_BARU] + rows, range_name="A1", value_input_option="RAW"))
    print(f"selesai. Log sekarang {len(rows)} baris, 9 kolom. Backup ada di '{backup_name}'.")


if __name__ == "__main__":
    main()
