# -*- coding: utf-8 -*-
"""Pasang tab 'Riwayat SO' — hasil SO tiap bulan bersebelahan, barang jadi baris.

    python3 -u add_riwayat_so.py            # pasang / perbarui tab
    python3 -u add_riwayat_so.py --uji      # pasang lalu cocokkan dengan Arsip Harian

Tab Arsip Harian menyimpan hasil SO memanjang: satu baris per tanggal per SKU.
Bagus sebagai catatan, payah untuk membandingkan — untuk tahu "bulan ini berapa,
bulan kemarin berapa" harus mencari dua baris yang berjauhan untuk tiap barang.

Tab ini bentuk lebarnya: barang jadi baris, bulan jadi kolom, terlama di kiri.

    Produk              Satuan   2026-07   2026-08   2026-09
    Thinwall DM 200RB   Trs           25        19        31

Catatan jujur: tab 'Arsip Bulanan' yang lama isinya data yang sama persis dan
dibuang 2026-08-25 dengan alasan duplikat Arsip Harian. Alasan itu benar untuk
bentuk MEMANJANG — barisnya memang sama karena SO dilakukan sebulan sekali. Tapi
bentuk LEBAR ini beda gunanya: bulan bersebelahan, jadi bisa dibandingkan sekali
lihat. Yang dibuang bentuknya, bukan datanya.

Pakai `pivot` bawaan QUERY, BUKAN ARRAYFORMULA(SUMIFS(...)): SUMIFS tidak
ter-vektor di dalam ARRAYFORMULA, tiap baris ikut hasil baris pertama. Kolom bulan
ikut sendiri tiap ada SO baru — tidak ada daftar bulan yang ditulis di kode.

Locale sheet `in_ID`: pemisah argumen `;` dan pemisah kolom array `\\`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Riwayat SO"

# Log: A Waktu, B Staff, C Rak, D Produk, E Rincian, F Qty, G Satuan, H ED, I SKU.
# Col1=bulan, Col2=Produk, Col3=Satuan, Col4=Qty, Col5=Rak
SUMBER = (r"{ARRAYFORMULA(LEFT(Log!A2:A;7))\Log!D2:D\Log!G2:G\Log!F2:F\Log!C2:C}")

PER_BULAN = ('=IFERROR(QUERY(' + SUMBER +
             ';"select Col2, Col3, sum(Col4) where Col2 is not null and Col2 <> \'\' '
             "group by Col2, Col3 pivot Col1 "
             "label Col2 'Produk', Col3 'Satuan'\";0);\"belum ada hasil SO\")")

# Blok kedua: bulan terakhir dipecah per gudang, supaya ketahuan sebarannya waktu
# SO itu -- beda dengan tab Stok per Gudang yang menunjukkan keadaan SEKARANG.
BULAN_TERAKHIR = (
    '=IFERROR(QUERY(' + SUMBER +
    ';"select Col2, Col3, sum(Col4) where Col2 is not null and Col2 <> \'\' '
    "and Col1 = '\"&"
    'IFERROR(INDEX(SORT(UNIQUE(FILTER(ARRAYFORMULA(LEFT(Log!A2:A;7));Log!A2:A<>""));1;0);1;1);"")'
    "&\"' group by Col2, Col3 pivot Col5 "
    "label Col2 'Produk', Col3 'Satuan'\";0);\"belum ada hasil SO\")")

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# Bulan SO terakhir, buat judul blok kedua.
BULAN_JUDUL = ('="SO BULAN TERAKHIR, DIPECAH PER GUDANG  ("&'
               'IFERROR(INDEX(SORT(UNIQUE(FILTER(ARRAYFORMULA(LEFT(Log!A2:A;7));'
               'Log!A2:A<>""));1;0);1;1);"belum ada")&")"')


def pasang(ws):
    ws.clear()
    ws.update(values=[["HASIL SO TIAP BULAN  (terlama di kiri)"]], range_name="A1")
    ws.update(values=[[PER_BULAN]], range_name="A2", value_input_option="USER_ENTERED")
    # Blok kedua di kolom TETAP: jumlah baris blok pertama berubah mengikuti
    # banyaknya produk, jadi apa pun di bawahnya cepat atau lambat ketabrak.
    ws.update(values=[[BULAN_JUDUL]], range_name="P1", value_input_option="USER_ENTERED")
    ws.update(values=[[BULAN_TERAKHIR]], range_name="P2", value_input_option="USER_ENTERED")
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.format("P1", {"textFormat": {"bold": True}})
    ws.freeze(rows=2, cols=2)


def buka(sh):
    import gspread
    try:
        ws = sh.worksheet(TAB)
        if ws.col_count < 24 or ws.row_count < 6000:
            ws.resize(rows=max(ws.row_count, 6000), cols=max(ws.col_count, 24))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(TAB, rows=6000, cols=24)


def jalan(pakai_uji):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    ws = buka(sh)
    pasang(ws)
    time.sleep(3)
    print(f"Tab '{TAB}' terpasang.", flush=True)

    isi = ws.get_all_values()
    galat = [f"{chr(64 + j + 1)}{i}" for i, r in enumerate(isi, 1) for j, c in enumerate(r)
             if str(c).strip().rstrip("!?") in
             ("#ERROR", "#REF", "#VALUE", "#NAME", "#N/A", "#DIV/0")]
    if galat:
        print("GALAT FORMULA:", galat[:5], flush=True)
        return 1
    print("Tidak ada galat formula.", flush=True)

    # Blok pertama hanya kolom A..O; mulai P itu blok kedua.
    baris = [r[:15] for r in isi[1:] if r and any(str(x).strip() for x in r[:15])]
    print(f"{max(len(baris) - 1, 0)} produk, "
          f"{len([x for x in baris[0][2:] if str(x).strip()]) if baris else 0} kolom bulan",
          flush=True)
    for r in baris[:6]:
        print("   ", [x for x in r if str(x).strip()][:8], flush=True)

    if not pakai_uji:
        return 0
    if not baris or baris[0][0].strip() != "Produk":
        print("   GAGAL: baris judul tidak berlabel Produk:", baris[0][:3] if baris else None,
              flush=True)
        return 1

    # Cocokkan total tiap baris dengan Arsip Harian. Pivot yang salah kolom tidak
    # menghasilkan error, cuma angka yang pindah tempat.
    arsip = sh.worksheet("Arsip Harian").get_all_values()[1:]
    harus = {}
    for r in arsip:
        if len(r) > 4 and r[2].strip():
            try:
                harus[r[2].strip()] = harus.get(r[2].strip(), 0) + float(r[4] or 0)
            except ValueError:
                pass
    gagal = []
    for r in baris[1:]:
        produk = r[0].strip()
        jml = 0.0
        for x in r[2:]:
            try:
                jml += float(str(x).replace(".", "").replace(",", ".") or 0)
            except ValueError:
                pass
        if produk in harus and abs(jml - harus[produk]) > 0.001:
            gagal.append(f"{produk}: pivot {jml} vs Arsip Harian {harus[produk]}")
    if gagal:
        for g in gagal:
            print("   GAGAL:", g, flush=True)
        return 1
    print(f"   {len(baris) - 1} produk cocok dengan Arsip Harian LOLOS", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="pasang lalu cocokkan dengan Arsip Harian")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
