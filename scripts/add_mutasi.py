# -*- coding: utf-8 -*-
"""Tambah tab 'Mutasi' + 'Rekap Mutasi' di sheet 'SO Toko Kartini'.

Seperti add_arsip_bulanan.py dan BERBEDA dari setup_sheet.py, skrip ini hanya
menyentuh dua tab barunya sendiri -- Rekap!G1 tidak dikosongkan, formula Log /
Rekap / Template Olsera / Arsip tidak disentuh. Jadi aman dijalankan kapan saja,
termasuk saat SO sedang berjalan, dan aman diulang.
"""
import socket
import time
import warnings

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

# IPv6 ke Google menggantung di jaringan toko (SYN-SENT ke 2001:4860:... tak pernah
# berbalas), jadi skrip diam bermenit-menit tanpa output. Paksa IPv4.
_getaddrinfo_asli = socket.getaddrinfo


def _ipv4_saja(host, port, family=0, type=0, proto=0, flags=0):
    return _getaddrinfo_asli(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_saja

KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# Tab Mutasi -- 11 kolom, urutannya dikunci buildMutasiRows() di
# supabase/functions/upload-mutasi/rows.ts. Kalau salah satu berubah, ubah keduanya.
MUTASI_HEADER = [
    "Waktu", "Staff", "Jenis", "Dari", "Ke", "Produk",
    "Rincian", "Qty", "Satuan", "SKU", "Nota",
]

REKAP_HEADER = ["Tanggal", "Jenis", "Dari", "Ke", "SKU", "Produk", "Satuan", "Total Qty"]

# Rekap Mutasi: semua tanggal, terbaru di atas -- bukan satu hari seperti tab Rekap.
# Alasannya mutasi dibaca sebagai riwayat ("kapan terakhir Gulaku naik ke display"),
# dan angka kumulatifnya nanti jadi bahan hitung saldo per lokasi.
#
# Col1=Tanggal, Col2=Jenis, Col3=Dari, Col4=Ke, Col5=Produk, Col6=SKU, Col7=Satuan, Col8=Qty
#
# Agregatnya pakai QUERY group by, BUKAN ARRAYFORMULA(SUMIFS(...)): SUMIFS tidak
# ter-vektor di dalam ARRAYFORMULA, tiap baris ikut hasil baris pertama. Pernah bikin
# dua SKU beda sama-sama tampil 75 di tab Rekap.
#
# Locale sheet in_ID: pemisah argumen ';' dan pemisah kolom array '\'.
SUMBER = (
    'ARRAYFORMULA(LEFT(Mutasi!A2:A;10))\\'
    'Mutasi!C2:C\\Mutasi!D2:D\\Mutasi!E2:E\\Mutasi!F2:F\\Mutasi!J2:J\\Mutasi!I2:I\\Mutasi!H2:H'
)

REKAP_MUTASI = (
    '=IFERROR(QUERY({' + SUMBER + '};'
    '"select Col1, Col2, Col3, Col4, Col6, Col5, Col7, sum(Col8) '
    "where Col6<>'' "
    'group by Col1, Col2, Col3, Col4, Col6, Col5, Col7 '
    "order by Col1 desc, Col5 label sum(Col8) ''\";0);\"\")"
)


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except gspread.exceptions.WorksheetNotFound:
            raise  # bukan galat jaringan -- mengulangnya cuma buang 15 detik
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", flush=True)
            time.sleep(delay)


def get_or_add_worksheet(sh, title, rows, cols):
    try:
        ws = retry(lambda: sh.worksheet(title))
        if ws.col_count < cols or ws.row_count < rows:
            new_rows, new_cols = max(ws.row_count, rows), max(ws.col_count, cols)
            retry(lambda: ws.resize(rows=new_rows, cols=new_cols))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return retry(lambda: sh.add_worksheet(title, rows=rows, cols=cols))


def main():
    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))

    tab_lama = [ws.title for ws in retry(lambda: sh.worksheets())]
    print(f"Tab saat ini: {tab_lama}", flush=True)

    mutasi = get_or_add_worksheet(sh, "Mutasi", rows=50000, cols=11)
    isi = retry(lambda: mutasi.get_all_values())
    baris_data = max(len(isi) - 1, 0)
    print(f"Tab Mutasi berisi {baris_data} baris data", flush=True)

    # Hanya baris judul yang ditulis ulang -- data yang sudah ada tidak disentuh.
    retry(lambda: mutasi.update(values=[MUTASI_HEADER], range_name="A1:K1"))
    retry(lambda: mutasi.format("A1:K1", {"textFormat": {"bold": True}}))

    rekap = get_or_add_worksheet(sh, "Rekap Mutasi", rows=50000, cols=8)
    retry(lambda: rekap.update(values=[REKAP_HEADER], range_name="A1:H1"))
    retry(lambda: rekap.format("A1:H1", {"textFormat": {"bold": True}}))
    retry(lambda: rekap.update(values=[[REKAP_MUTASI]], range_name="A2", raw=False))
    time.sleep(3)

    cek = retry(lambda: rekap.get_values("A2:H3"))
    print(f"Rekap Mutasi A2:H3: {cek}", flush=True)

    if baris_data:
        tanggal_terakhir = max(r[0][:10] for r in isi[1:] if r and r[0])
        assert cek and cek[0][0] == tanggal_terakhir, f"formula Rekap Mutasi gagal: {cek}"
        assert len(cek[0]) == 8 and cek[0][4] and cek[0][7], f"kolom Rekap Mutasi kurang: {cek}"
        print("Rekap Mutasi formula verified [OK]", flush=True)
    else:
        print("Mutasi masih kosong -- formula terpasang, belum bisa diuji isinya", flush=True)

    print("Selesai. Tab Log/Rekap/Template Olsera/Arsip tidak disentuh.", flush=True)


if __name__ == "__main__":
    main()
