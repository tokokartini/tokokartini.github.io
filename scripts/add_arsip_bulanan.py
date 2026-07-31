# -*- coding: utf-8 -*-
"""Tambah tab 'Arsip Bulanan' di sheet 'SO Toko Kartini'.

Berbeda dari setup_sheet.py, skrip ini HANYA menyentuh tab Arsip Bulanan --
Rekap!G1 tidak dikosongkan, jadi aman dijalankan kapan saja termasuk saat SO
sedang berjalan.
"""
import time
import warnings

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# Sama seperti setup_sheet.py: awalan "STOK " hanya di tab output.
PRODUK_STOK = 'ARRAYFORMULA(IF(Log!D2:D="";"";"STOK "&Log!D2:D))'

# Log 9 kolom: kolom disusun ulang jadi Satuan, SKU, Qty supaya nomor Col di
# string QUERY tetap sama seperti versi Log 8 kolom. Sama persis dengan
# LOG_TAIL di setup_sheet.py -- kalau salah satu berubah, ubah keduanya.
LOG_TAIL = 'Log!G2:G\\Log!I2:I\\Log!F2:F'

# Arsip bulanan: LEFT(Log!A;7) -> "2026-07". Kolom sumber sama persis dengan
# Arsip Harian, cuma tanggalnya dipotong sampai bulan.
# Col1=Bulan, Col2=Produk, Col3=Satuan, Col4=SKU, Col5=Qty
ARSIP_BULANAN = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;7))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
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
            print(f"retry {i + 1}: {type(e).__name__}")
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

    log = retry(lambda: sh.worksheet("Log"))
    isi_log = retry(lambda: log.get_all_values())
    bulan_terakhir = max((r[0][:7] for r in isi_log[1:] if r and r[0]), default="")
    print(f"Log berisi {max(len(isi_log) - 1, 0)} baris, bulan terbaru: {bulan_terakhir or '(kosong)'}")

    ws = get_or_add_worksheet(sh, "Arsip Bulanan", rows=50000, cols=5)
    retry(lambda: ws.update(values=[["Bulan", "SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:E1"))
    retry(lambda: ws.update(values=[[ARSIP_BULANAN]], range_name="A2", raw=False))
    time.sleep(3)

    cek = retry(lambda: ws.get_values("A2:E3"))
    print(f"Arsip Bulanan A2:E3: {cek}")
    if bulan_terakhir:
        assert cek and cek[0][0] == bulan_terakhir, f"formula Arsip Bulanan gagal: {cek}"
        assert len(cek[0]) == 5 and cek[0][1] and cek[0][4], f"kolom Arsip Bulanan kurang: {cek}"
        print("Arsip Bulanan formula verified [OK]")
    else:
        print("Log masih kosong -- formula terpasang, belum bisa diuji isinya")


if __name__ == "__main__":
    main()
