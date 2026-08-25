# -*- coding: utf-8 -*-
"""Pasang tab 'Stok per Gudang' — barang jadi baris, gudang jadi kolom.

    python3 -u add_stok_gudang.py            # pasang / perbarui tab
    python3 -u add_stok_gudang.py --uji      # pasang lalu periksa angkanya

Tab Stok bentuknya memanjang: satu baris per lokasi per barang. Bagus untuk
dihitung, payah untuk dibaca — satu barang yang ada di lima gudang jadi lima baris
yang berjauhan, dan pertanyaan "barang ini di gudang mana saja" perlu menyisir
seluruh tab.

Tab ini bentuk silangnya:

    Produk              Packaging  Bahan Kue  Ciherang  Display  Total
    Thinwall DM 200RB          18          0         0       19     37

Pakai `pivot` bawaan QUERY, BUKAN ARRAYFORMULA(SUMIFS(...)). Alasannya bukan
selera: SUMIFS tidak ter-vektor di dalam ARRAYFORMULA, tiap baris ikut hasil baris
pertama. Pernah bikin dua SKU beda qty 75 dan 22 sama-sama ditulis 75
(2026-07-30). `pivot` mengerjakan hal yang sama tanpa jebakan itu, dan kolomnya
ikut sendiri kalau ada gudang baru — tidak ada daftar lokasi yang ditulis di kode.

Sumbernya tab Stok, yang baris 1-nya penanda dan judulnya di baris 2, jadi datanya
mulai `A3`.

Locale sheet `in_ID`: pemisah argumen `;`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Stok per Gudang"

# Tab Stok: A Lokasi, B SKU, C Produk, D Satuan, ..., J Sisa, K HPP, L Nilai Sisa.
# Dua blok: qty per gudang, lalu nilai rupiah per gudang di bawahnya.
QTY = ('=IFERROR(QUERY(Stok!A3:L;'
       '"select C, D, sum(J) where C is not null and C <> \'\' '
       'group by C, D pivot A '
       'label C \'Produk\', D \'Satuan\'";0);"belum ada stok — jalankan hitung saldo")')

# Blok total ditaruh di kolom TETAP (J), bukan di bawah blok pivot: jumlah baris
# pivot berubah mengikuti banyaknya produk, jadi apa pun yang ditaruh di bawahnya
# cepat atau lambat ketabrak. Jumlah kolom pivot paling banyak 2 + jumlah lokasi,
# dan lokasi ada lima, jadi kolom J selalu aman.
TOTAL = ('=IFERROR(QUERY(Stok!A3:L;'
         '"select C, D, sum(J), sum(L) where C is not null and C <> \'\' '
         'group by C, D order by sum(L) desc '
         'label C \'Produk\', D \'Satuan\', sum(J) \'Total Qty\', sum(L) \'Nilai\'";0);'
         '"belum ada stok")')

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# Penanda basi menumpang tab Stok: kalau angka di sana lama, yang di sini ikut lama.
PENANDA = '=IFERROR(Stok!A1;"tab Stok belum ada")'


def pasang(ws):
    ws.clear()
    ws.update(values=[[PENANDA]], range_name="A1", value_input_option="USER_ENTERED")
    ws.update(values=[["JUMLAH BARANG PER GUDANG"]], range_name="A3")
    ws.update(values=[[QTY]], range_name="A4", value_input_option="USER_ENTERED")
    ws.update(values=[["TOTAL SEMUA GUDANG  (termahal di atas)"]], range_name="J3")
    ws.update(values=[[TOTAL]], range_name="J4", value_input_option="USER_ENTERED")
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.format("A3:J3", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)


def buka(sh):
    import gspread
    try:
        ws = sh.worksheet(TAB)
        if ws.col_count < 15 or ws.row_count < 6000:
            ws.resize(rows=max(ws.row_count, 6000), cols=max(ws.col_count, 15))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(TAB, rows=6000, cols=15)


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

    # HANYA kolom A..I: mulai kolom J itu blok TOTAL, bukan bagian pivot. Tanpa
    # batas ini, pemeriksaan di bawah ikut menjumlahkan nilai rupiah ke dalam qty.
    baris = [r[:9] for r in isi[3:] if r and any(str(x).strip() for x in r[:9])]
    print(f"{max(len(baris) - 1, 0)} produk, "
          f"{len([x for x in baris[0][2:] if str(x).strip()]) if baris else 0} kolom lokasi",
          flush=True)
    if not baris or baris[0][0].strip() != "Produk":
        print("   GAGAL: baris judul pivot tidak berlabel Produk:",
              baris[0][:4] if baris else None, flush=True)
        return 1
    for r in baris[:6]:
        print("   ", [x for x in r if str(x).strip()][:8], flush=True)

    if not pakai_uji:
        return 0

    # Cocokkan total tiap baris dengan jumlah di tab Stok — pivot yang salah kolom
    # tidak menghasilkan error, cuma angka yang pindah tempat.
    stok = sh.worksheet("Stok").get_all_values()[2:]
    harus = {}
    for r in stok:
        if len(r) > 9 and r[2].strip():
            try:
                harus[r[2].strip()] = harus.get(r[2].strip(), 0) + float(r[9] or 0)
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
            gagal.append(f"{produk}: pivot {jml} vs tab Stok {harus[produk]}")
    if gagal:
        for g in gagal:
            print("   GAGAL:", g, flush=True)
        return 1
    print(f"   {len(baris) - 1} produk cocok dengan tab Stok LOLOS", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="pasang lalu cocokkan dengan tab Stok")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
