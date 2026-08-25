# -*- coding: utf-8 -*-
"""Pasang baris judul tab 'Mutasi' di sheet 'SO Toko Kartini'.

BERBEDA dari setup_sheet.py, skrip ini hanya menyentuh baris judul tab Mutasi --
isinya tidak, tab lain tidak. Aman dijalankan kapan saja, termasuk saat SO sedang
berjalan, dan aman diulang.

Tab 'Rekap Mutasi' dulu ikut dibuat di sini, sekarang tidak lagi: tab itu
mengagregat tab Mutasi yang sendirinya sudah satu baris per barang dan mudah
dibaca. Yang menjawab pertanyaan sungguhan adalah tab Stok (akibatnya pada stok),
Barang Rusak (yang hangus, lengkap rupiahnya), dan Cari Barang (riwayat satu
barang). Rekap Mutasi duduk di tengah tanpa pekerjaan, jadi dibuang.
"""
import os
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

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# Tab Mutasi -- 12 kolom, urutannya dikunci buildMutasiRows() di
# supabase/functions/upload-mutasi/rows.ts. Kalau salah satu berubah, ubah keduanya.
MUTASI_HEADER = [
    "Waktu", "Staff", "Jenis", "Dari", "Ke", "Produk",
    "Rincian", "Qty", "Satuan", "SKU", "Nota", "Sebab",
]




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

    mutasi = get_or_add_worksheet(sh, "Mutasi", rows=50000, cols=12)
    isi = retry(lambda: mutasi.get_all_values())
    baris_data = max(len(isi) - 1, 0)
    print(f"Tab Mutasi berisi {baris_data} baris data", flush=True)

    # Hanya baris judul yang ditulis ulang -- data yang sudah ada tidak disentuh.
    retry(lambda: mutasi.update(values=[MUTASI_HEADER], range_name="A1:L1"))
    retry(lambda: mutasi.format("A1:L1", {"textFormat": {"bold": True}}))

    print("Selesai. Isi tab Mutasi dan tab lain tidak disentuh.", flush=True)


if __name__ == "__main__":
    main()
