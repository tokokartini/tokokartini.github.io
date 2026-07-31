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
    """values = get_all_values() termasuk header. Balikkan (rows, truncated_info)."""
    rows = []
    truncated = []  # List of (produk, extra_cols) for rows with data past column H

    for raw in values[1:]:
        row = list(raw) + [""] * (8 - len(raw))
        waktu, staff, rack, produk, satuan, sku, qty, ed = row[:8]
        if not str(produk).strip():
            continue

        # Check for data past column H (8 columns in old layout)
        extra_values = [str(v).strip() for v in raw[8:] if v and str(v).strip()]
        if extra_values:
            truncated.append((str(produk), extra_values))

        rows.append([waktu, staff, rack, produk, "", qty, satuan, ed, sku])

    return rows, truncated


def main():
    tulis = "--tulis" in sys.argv

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))
    ws = retry(lambda: sh.worksheet(TAB))

    values = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))

    # Penjaga: kalau header sudah 9 kolom, migrasi pernah jalan. Menjalankannya
    # dua kali akan menggeser kolom untuk kedua kalinya dan merusak datanya.
    #
    # Header teks saja tidak cukup dipercaya: setup_sheet.py menulis ulang
    # Log!A1:I1 tanpa menyentuh data, jadi kalau operator menjalankannya sebelum
    # migrasi, header akan berbunyi "sudah baru" padahal data masih 8 kolom lama.
    # Guard di sini karena itu juga menuntut BUKTI DI DATA: minimal satu baris
    # punya kolom I (SKU baru) terisi. Kalau header baru tapi kolom I kosong di
    # semua baris, perlakukan sebagai belum-migrasi dan lanjutkan.
    header = (values[0] if values else [])
    if headers_match(header, HEADER_BARU, 9):
        col_i_terisi = any(
            len(row) > 8 and str(row[8]).strip() for row in values[1:]
        )
        if col_i_terisi:
            print("BATAL: header Log sudah susunan baru, migrasi tidak perlu diulang.")
            return
        print(
            "Header Log sudah bertuliskan susunan baru, tapi tidak ada baris data dengan "
            "kolom I (SKU) terisi -- kemungkinan cuma header yang ditimpa (mis. oleh "
            "setup_sheet.py) sementara data masih 8 kolom lama. Melanjutkan migrasi "
            "memakai data yang ada, mengabaikan teks header."
        )
    elif not headers_match(header, HEADER_LAMA, 8):
        print(
            f"BATAL: header Log tak dikenali: {header}. "
            f"Kalau Log kosong akibat migrasi yang terhenti di tengah (batch_clear sukses tapi "
            f"update gagal), pulihkan isi tab 'Log backup kolom <tanggal>' ke Log lalu jalankan ulang."
        )
        return

    rows, truncated = pindah(values)
    print(f"Log: {len(values) - 1} baris -> {len(rows)} baris")
    print("\ncontoh 5 baris hasil:")
    for r in rows[:5]:
        print("  " + " | ".join(str(x) for x in r))

    # Lapor kolom yang akan hilang saat migrasi
    if truncated:
        print(f"\nPerhatian: {len(truncated)} baris punya data di kolom > H yang akan hilang:")
        for produk, extras in truncated[:5]:
            print(f"  {produk} | data hilang: {extras}")
        if len(truncated) > 5:
            print(f"  ... dan {len(truncated) - 5} baris lagi")

    if not tulis:
        print("\nDRY-RUN. Tidak ada yang ditulis. Jalankan lagi dengan --tulis untuk menulis.")
        return

    # Hanya saat menulis: ubah ukuran kolom terlebih dahulu
    if ws.col_count < 9:
        retry(lambda: ws.resize(rows=ws.row_count, cols=9))

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

    # Tulis DULU, baru bersihkan sisa baris lama di bawahnya. Kalau urutannya
    # dibalik (clear lalu update), ada jendela waktu di mana Log kosong sama
    # sekali -- upload yang masuk tepat di jendela itu akan ditandai terkirim
    # (count_entries.uploaded_at diisi) padahal baris barunya lalu tertimpa
    # update ini dan tidak pernah ada di Log maupun di backup. Dengan menulis
    # dulu, upload yang menyelinap di jendela (sekarang jauh lebih sempit, cuma
    # antara update dan batch_clear) paling buruk selamat sebagai baris bentuk
    # aneh di bagian yang nanti dibersihkan -- kelihatan, bukan lenyap.
    n_baris = len(rows) + 1  # header + data baru
    retry(lambda: ws.update(values=[HEADER_BARU] + rows, range_name="A1", value_input_option="RAW"))
    sisa_akhir = max(len(values), len(rows) + 1) + 10
    retry(lambda: ws.batch_clear([f"A{n_baris + 1}:I{sisa_akhir}"]))
    print(f"selesai. Log sekarang {len(rows)} baris, 9 kolom. Backup ada di '{backup_name}'.")

    # Verifikasi: baca ulang jumlah baris supaya operator lihat kalau ada
    # upload yang menyelinap di jendela tabrakan sempit di atas.
    cek_akhir = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))
    baris_akhir = len(cek_akhir)
    if baris_akhir > n_baris:
        print(
            f"PERHATIAN: Log sekarang berisi {baris_akhir} baris (termasuk header), "
            f"melebihi {n_baris} yang diharapkan -- kemungkinan ada upload yang menyelinap "
            f"selama migrasi. Periksa baris di bawah baris ke-{n_baris} secara manual."
        )
    else:
        print(f"verifikasi: Log berisi {baris_akhir} baris (termasuk header), sesuai harapan.")


if __name__ == "__main__":
    main()
