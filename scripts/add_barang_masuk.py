# -*- coding: utf-8 -*-
"""Pasang tab 'Barang Masuk' — kiriman supplier, terisi sendiri dari tab Mutasi.

    python3 -u add_barang_masuk.py            # pasang / perbarui tab
    python3 -u add_barang_masuk.py --uji      # pasang lalu periksa isinya

Semua yang perlu dicatat waktu barang datang SUDAH direkam aplikasi lewat menu
**Barang Datang**: produk, qty, satuan, gudang tujuan, supplier (kolom Nota), dan
siapa yang mencatat. Semuanya mendarat di tab Mutasi dengan Jenis = 'Datang'.

Tab ini cuma menyaring dan merapikannya. Formula, jadi tidak ada yang perlu
diketik ulang — dan itu intinya: mencatat dua kali berarti dua angka yang cepat
atau lambat berbeda, dan tidak ada cara tahu mana yang benar.

Ada juga blok rekap per supplier di kanan, buat tahu siapa yang paling sering
kirim dan berapa nilainya.

Locale sheet `in_ID`: pemisah argumen `;` dan pemisah kolom array `\\`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Barang Masuk"

# Mutasi: A Waktu, B Staff, C Jenis, D Dari, E Ke, F Produk, G Rincian, H Qty,
# I Satuan, J SKU, K Nota, L Sebab.
# Col1..Col8 = Waktu, Produk, Rincian, Qty, Satuan, Ke, Nota, Staff; Col9 = Jenis
SUMBER = (r"{Mutasi!A2:A\Mutasi!F2:F\Mutasi!G2:G\Mutasi!H2:H\Mutasi!I2:I"
          r"\Mutasi!E2:E\Mutasi!K2:K\Mutasi!B2:B\Mutasi!C2:C\Mutasi!J2:J}")

RINCI = ('=IFERROR(QUERY(' + SUMBER +
         ';"select Col1, Col2, Col3, Col4, Col5, Col6, Col7, Col8, Col10 '
         "where Col9 = 'Datang' order by Col1 desc "
         "label Col1 'Waktu', Col2 'Produk', Col3 'Rincian', Col4 'Qty', "
         "Col5 'Satuan', Col6 'Masuk ke', Col7 'Supplier', Col8 'Dicatat', "
         "Col10 'SKU'\";0);\"belum ada barang datang tercatat\")")

# Nilai dihitung di kolom bantu: QUERY tidak bisa memanggil VLOOKUP ke tab lain.
NILAI = ('=ARRAYFORMULA(IF($I$3:$I="";"";'
         'IFERROR($D$3:$D*VLOOKUP($I$3:$I;Harga!$A:$E;5;FALSE);"")))')

PER_SUPPLIER = ('=IFERROR(QUERY(' + SUMBER +
                ';"select Col7, count(Col2), sum(Col4) where Col9 = \'Datang\' '
                "group by Col7 order by count(Col2) desc "
                "label Col7 'Supplier', count(Col2) 'Kiriman', sum(Col4) 'Total Qty'\";0);"
                '"belum ada data")')

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def pasang(ws):
    ws.clear()
    ws.update(values=[["KIRIMAN SUPPLIER — terisi sendiri dari menu Barang Datang di aplikasi"]],
              range_name="A1")
    ws.update(values=[[RINCI]], range_name="A2", value_input_option="USER_ENTERED")
    ws.update(values=[["Nilai HPP"]], range_name="J2")
    ws.update(values=[[NILAI]], range_name="J3", value_input_option="USER_ENTERED")
    ws.update(values=[["PER SUPPLIER"]], range_name="L1")
    ws.update(values=[[PER_SUPPLIER]], range_name="L2", value_input_option="USER_ENTERED")
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.format("A2:J2", {"textFormat": {"bold": True}})
    ws.format("L1", {"textFormat": {"bold": True}})
    ws.freeze(rows=2)


def buka(sh):
    import gspread
    try:
        ws = sh.worksheet(TAB)
        if ws.col_count < 16 or ws.row_count < 20000:
            ws.resize(rows=max(ws.row_count, 20000), cols=max(ws.col_count, 16))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(TAB, rows=20000, cols=16)


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

    baris = [r[:10] for r in isi[1:] if r and any(str(x).strip() for x in r[:10])]
    print(f"{max(len(baris) - 1, 0)} kiriman", flush=True)
    for r in baris[:5]:
        print("   ", [x for x in r if str(x).strip()][:9], flush=True)

    if not pakai_uji:
        return 0

    gagal = []
    if not baris or baris[0][0].strip() != "Waktu":
        gagal.append(f"baris judul salah: {baris[0][:4] if baris else None}")
    # Cocokkan jumlah barisnya dengan tab Mutasi jenis Datang.
    mutasi = sh.worksheet("Mutasi").get_all_values()[1:]
    harus = sum(1 for r in mutasi if len(r) > 2 and r[2].strip() == "Datang")
    if len(baris) - 1 != harus:
        gagal.append(f"jumlah kiriman {len(baris) - 1}, di tab Mutasi ada {harus}")
    # Jenis selain Datang tidak boleh bocor.
    bukan = [r for r in baris[1:] if r[5].strip() == "Barang Rusak"]
    if bukan:
        gagal.append(f"jenis selain Datang ikut masuk: {bukan[:2]}")
    if gagal:
        for g in gagal:
            print("   GAGAL:", g, flush=True)
        return 1
    print(f"   {harus} kiriman cocok dengan tab Mutasi LOLOS", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="pasang lalu cocokkan dengan tab Mutasi")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
