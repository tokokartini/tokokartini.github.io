# -*- coding: utf-8 -*-
"""Pasang tab 'Cari Barang' — satu barang, semua faktanya di satu layar.

    python3 -u add_cari_barang.py            # pasang / perbarui tab
    python3 -u add_cari_barang.py --uji      # pasang lalu periksa pakai barang sungguhan

Ini menjawab pertanyaan yang paling sering diajukan ke sheet ini: "barang X ada
berapa, di mana". Sebelumnya harus membuka tab Stok, lalu Kadaluarsa, lalu Mutasi,
lalu Selisih SO, dan mencocokkan sendiri.

Ketik nama atau SKU di `B1`, lima blok di bawahnya terisi sendiri. Semuanya
formula, jadi tidak ada yang perlu dijalankan.

Pencarian pakai `contains` yang tidak peduli huruf besar-kecil, dan mencocokkan ke
nama MAUPUN SKU sekaligus — orang gudang mengetik nama, orang kantor menempel SKU.

Tiap blok dibatasi `limit` supaya tumpahannya tidak pernah menabrak blok di
bawahnya. Batasnya ditulis di judul blok, jadi kalau terpotong ketahuan.

Locale sheet `in_ID`: pemisah argumen `;`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Cari Barang"

# Bagian pencocokan yang dipakai berulang. `nama` dan `sku` = huruf kolomnya.
def _cocok(nama, sku):
    return (f"lower({nama}) contains '\"&LOWER($B$1)&\"' "
            f"or lower({sku}) contains '\"&LOWER($B$1)&\"'")


def _blok(judul, baris, rumus):
    return (judul, baris, rumus)


# Tab Stok: baris 1 penanda, 2 judul, data mulai baris 3.
# A Lokasi B SKU C Produk D Satuan E HasilSO F TglSO G Masuk H Keluar I Terjual
# J Sisa K HPP L Nilai M Catatan
STOK = ('=IF($B$1="";"";IFERROR(QUERY(Stok!A3:M;'
        '"select A, D, E, G, H, I, J, L where ' + _cocok("C", "B") + ' '
        "order by J desc limit 10 "
        "label A 'Lokasi', D 'Satuan', E 'Hasil SO', G 'Masuk', H 'Keluar', "
        "I 'Terjual', J 'Sisa', L 'Nilai'\";0);\"tidak ada stok tercatat\"))")

# Tab Harga: A SKU B Produk C Satuan D Isi E HPP F Harga Jual G Slot H Kategori
HARGA = ('=IF($B$1="";"";IFERROR(QUERY(Harga!A2:H;'
         '"select B, C, D, E, F, A where ' + _cocok("B", "A") + ' '
         "order by D desc limit 6 "
         "label B 'Produk', C 'Satuan', D 'Isi', E 'HPP', F 'Harga Jual', A 'SKU'\";0);"
         '"tidak ada di Master Pricelist"))')

# Tab Kadaluarsa: A ED B SKU C Produk D Satuan E Qty F Rak G Staff H Waktu
# I SisaHari J Status K Nilai
ED = ('=IF($B$1="";"";IFERROR(QUERY(Kadaluarsa!A2:K;'
      '"select A, F, E, I, J where (' + _cocok("C", "B") + ') '
      "order by A limit 5 "
      "label A 'ED', F 'Lokasi', E 'Qty', I 'Sisa Hari', J 'Status'\";0);"
      '"tidak ada tanggal ED tercatat"))')

# Tab Mutasi: A Waktu B Staff C Jenis D Dari E Ke F Produk G Rincian H Qty
# I Satuan J SKU K Nota L Sebab
MUTASI = ('=IF($B$1="";"";IFERROR(QUERY(Mutasi!A2:L;'
          '"select A, C, D, E, H, L, B where (' + _cocok("F", "J") + ') '
          "order by A desc limit 10 "
          "label A 'Waktu', C 'Jenis', D 'Dari', E 'Ke', H 'Qty', L 'Sebab', B 'Staff'\";0);"
          '"belum pernah dimutasi"))')

# Tab Selisih SO: baris 1 penanda, 2 judul, data mulai 3.
# A TglSO B Lokasi C SKU D Produk E Satuan F Perkiraan G Hasil H Selisih I HPP
# J Nilai K Dasar
SELISIH = ('=IF($B$1="";"";IFERROR(QUERY(\'Selisih SO\'!A3:K;'
           '"select A, B, F, G, H, J where (' + _cocok("D", "C") + ') '
           "order by A desc limit 5 "
           "label A 'Tgl SO', B 'Lokasi', F 'Perkiraan', G 'Hasil Hitung', "
           "H 'Selisih', J 'Nilai'\";0);\"belum pernah ada selisih\"))")

# (judul blok, baris judul, rumus). Jaraknya sengaja lebar: tiap blok punya
# `limit`, dan jarak antar blok selalu lebih besar dari limit + baris judul QUERY.
BLOK = [
    ("STOK PER LOKASI  (10 teratas)", 4, STOK),
    ("HARGA PER SATUAN  (6 teratas)", 17, HARGA),
    ("TANGGAL ED TERDEKAT  (5 teratas)", 26, ED),
    ("MUTASI TERAKHIR  (10 terakhir)", 34, MUTASI),
    ("SELISIH SO TERAKHIR  (5 terakhir)", 47, SELISIH),
]

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def pasang(ws):
    ws.clear()
    ws.update(values=[["Cari barang:", ""],
                      ["ketik nama atau SKU di sebelah, sebagian nama juga boleh", ""]],
              range_name="A1")
    for judul, baris, rumus in BLOK:
        ws.update(values=[[judul]], range_name=f"A{baris}")
        ws.update(values=[[rumus]], range_name=f"A{baris + 1}",
                  value_input_option="USER_ENTERED")
        ws.format(f"A{baris}", {"textFormat": {"bold": True}})
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.format("B1", {"backgroundColor": {"red": 1, "green": 0.98, "blue": 0.85},
                     "textFormat": {"bold": True}})
    ws.format("A2", {"textFormat": {"italic": True, "foregroundColor":
                                    {"red": 0.5, "green": 0.5, "blue": 0.5}}})
    ws.freeze(rows=2)


def buka(sh):
    import gspread
    try:
        ws = sh.worksheet(TAB)
        if ws.col_count < 12 or ws.row_count < 60:
            ws.resize(rows=max(ws.row_count, 60), cols=max(ws.col_count, 12))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(TAB, rows=60, cols=12)


def jalan(pakai_uji):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    ws = buka(sh)
    pasang(ws)
    time.sleep(2)
    print(f"Tab '{TAB}' terpasang.", flush=True)

    galat = [f"{c}{i}" for i, r in enumerate(ws.get_all_values(), 1)
             for c, sel in zip("ABCDEFGHIJKL", r)
             if str(sel).strip().rstrip("!?") in
             ("#ERROR", "#REF", "#VALUE", "#NAME", "#N/A", "#DIV/0")]
    if galat:
        print("GALAT FORMULA:", galat, flush=True)
        return 1
    print("Tidak ada galat formula (kotak cari masih kosong).", flush=True)

    if not pakai_uji:
        return 0

    # Uji pakai barang yang benar-benar ada datanya di sheet sekarang.
    ws.update(values=[["Thinwall"]], range_name="B1")
    time.sleep(4)
    isi = ws.get_all_values()
    gagal = []
    for judul, baris, _ in BLOK:
        potong = [r for r in isi[baris:baris + 12] if r and any(str(x).strip() for x in r)]
        print(f"\n   {judul}", flush=True)
        for r in potong[:4]:
            print("     ", [x for x in r if str(x).strip()][:8], flush=True)
        if not potong:
            gagal.append(f"blok '{judul}' kosong sama sekali")

    # Stok harus memuat kedua lokasi Thinwall.
    stok = " ".join(" ".join(r) for r in isi[4:16])
    for harus in ("Gudang Packaging", "Area Display"):
        if harus not in stok:
            gagal.append(f"blok STOK tidak memuat {harus}")

    ws.update(values=[[""]], range_name="B1")
    print("\n   kotak cari dikosongkan lagi", flush=True)
    if gagal:
        for g in gagal:
            print("   GAGAL:", g, flush=True)
        return 1
    print("   semua blok terisi LOLOS", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="pasang lalu coba cari barang sungguhan")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
