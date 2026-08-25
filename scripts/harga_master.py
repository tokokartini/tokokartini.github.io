# -*- coding: utf-8 -*-
"""Tarik HPP + harga jual dari Master Pricelist, tulis ke tab 'Harga'.

    python3 -u harga_master.py            # baca master, tulis tab Harga
    python3 -u harga_master.py --uji      # jalankan uji parsing, tanpa jaringan

Kenapa tab sendiri dan BUKAN kolom baru di tabel `products` Supabase: aplikasi
hitung stok tidak butuh harga sama sekali, dan menambah kolom di sana berarti
mengubah tiga berkas kembar (`sync_products.py`, `src/lib/parseMaster.js`,
`supabase/functions/sync-produk/index.ts`) plus migrasi DB. Risiko besar untuk
angka yang cuma dipakai di sheet. Tab Harga dibaca `hitung_saldo.py` dan
`saldo_display.py` lewat SKU untuk mengisi kolom Nilai.

Tiap produk di master punya sampai empat slot satuan, masing-masing dengan SKU,
HPP, dan harga jualnya sendiri. Pemetaan kolomnya sudah diuji lawan data asli
(`HPP HJ1 x isi = HPP Grosir`, cocok 32 baris, beda 0):

    slot     satuan  isi   HPP   harga jual   SKU
    Grosir     6      -     5        16       28
    HJ1        8      7     13       17       29
    HJ2       10      9     14       18       30
    HJ3       12     11     15       19       31

Harga jual boleh kosong (beberapa tingkat memang tidak dijual eceran) — dibiarkan
kosong, jangan ditebak dari tingkat lain.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Harga"
JUDUL = ["SKU", "Produk", "Satuan", "Isi", "HPP", "Harga Jual", "Slot", "Kategori"]

# (nama slot, kolom SKU, kolom satuan, kolom isi, kolom HPP, kolom harga jual)
# `isi` None = slot grosir, master tidak menuliskannya karena isinya 1 grosir.
SLOTS = [
    ("Grosir", 28, 6, None, 5, 16),
    ("HJ1", 29, 8, 7, 13, 17),
    ("HJ2", 30, 10, 9, 14, 18),
    ("HJ3", 31, 12, 11, 15, 19),
]


# --- Bagian murni ----------------------------------------------------------

def angka(raw):
    """`1.411.172` -> 1411172.0, `8.620,00` -> 8620.0, kosong / `-` -> None.

    Master ditulis dengan format Indonesia: titik ribuan, koma desimal.
    """
    s = str(raw if raw is not None else "").strip()
    if not s or s == "-":
        return None
    s = s.replace("Rp", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    if not s or s in (".", "-"):
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return n


def parse_harga(rows):
    """Kembalikan (baris, lewat) dari baris mentah tab Master Pricelist New.

    `rows` sudah termasuk dua baris judul — dipotong di sini supaya sama persis
    dengan `sync_products.py` dan `parseMaster.js`.
    """
    baris = []
    seen = set()
    lewat = {"tanpa nama": 0, "pemisah kategori": 0, "satuan kosong": 0,
             "SKU kembar": 0, "tanpa HPP": 0}

    kategori = ""
    for raw in rows[2:]:
        row = list(raw) + [""] * (32 - len(raw))
        nama = str(row[3]).strip()
        kolom0 = str(row[0]).strip()
        # Baris pemisah `=== Packaging ===` menandai kategori berikutnya.
        if kolom0.startswith("==="):
            kategori = kolom0.strip("= ").strip()
            lewat["pemisah kategori"] += 1
            continue
        if not nama:
            lewat["tanpa nama"] += 1
            continue
        if kolom0:
            kategori = kolom0

        for nama_slot, sku_i, sat_i, isi_i, hpp_i, jual_i in SLOTS:
            sku = str(row[sku_i]).strip()
            if not sku:
                continue
            satuan = str(row[sat_i]).strip()
            # SKU tetap ditulis master walau satuannya tidak dipakai produk ini.
            if not satuan:
                lewat["satuan kosong"] += 1
                continue
            if sku in seen:
                lewat["SKU kembar"] += 1
                continue
            seen.add(sku)

            hpp = angka(row[hpp_i])
            jual = angka(row[jual_i])
            if hpp is None:
                lewat["tanpa HPP"] += 1
            isi = 1.0 if isi_i is None else angka(row[isi_i])
            baris.append([
                sku, nama, satuan,
                "" if isi is None else _rapi(isi),
                "" if hpp is None else _rapi(hpp),
                "" if jual is None else _rapi(jual),
                nama_slot, kategori,
            ])
    return baris, lewat


def _rapi(x):
    return int(x) if float(x).is_integer() else round(float(x), 2)


# --- Uji --------------------------------------------------------------------

def uji():
    assert angka("1.411.172") == 1411172.0
    assert angka("8.620,00") == 8620.0
    assert angka("70.558,60") == 70558.60
    assert angka("500") == 500.0
    assert angka("") is None and angka("-") is None and angka(None) is None
    assert angka("abc") is None
    assert angka("Rp 12.000") == 12000.0

    judul = [[""] * 32, [""] * 32]
    r = [""] * 32
    r[0], r[3] = "Packaging", "Klip Merah Putih 4*6cm"
    r[6], r[5], r[16], r[28] = "Bal (20 Kg)", "1.411.172", "1.560.000", "KLP-G"
    r[8], r[7], r[13], r[17], r[29] = "Kg (4 Pack)", "20", "70.558,60", "", "KLP-1"
    r[10], r[9], r[14], r[18], r[30] = "Pack (10 Bks)", "80", "17.639,65", "22.000", "KLP-2"
    # slot HJ3 SKU ada tapi satuannya kosong -> harus dilewat, bukan dianggap ada
    r[12], r[31] = "", "KLP-3"

    pemisah = [""] * 32
    pemisah[0] = "=== Bahan Kue ==="
    kosong = [""] * 32
    kembar = [""] * 32
    kembar[3], kembar[6], kembar[5], kembar[28] = "Produk Lain", "Pack", "1.000", "KLP-G"

    baris, lewat = parse_harga(judul + [r, pemisah, kosong, kembar])
    per = {b[0]: b for b in baris}

    assert set(per) == {"KLP-G", "KLP-1", "KLP-2"}, f"slot salah: {sorted(per)}"
    assert per["KLP-G"][4] == 1411172 and per["KLP-G"][5] == 1560000, per["KLP-G"]
    assert per["KLP-G"][3] == 1, f"grosir isinya 1: {per['KLP-G']}"
    assert per["KLP-1"][4] == 70558.6, per["KLP-1"]
    assert per["KLP-1"][5] == "", f"harga jual kosong jangan ditebak: {per['KLP-1']}"
    assert per["KLP-2"][3] == 80 and per["KLP-2"][5] == 22000, per["KLP-2"]
    assert per["KLP-2"][7] == "Packaging", f"kategori salah: {per['KLP-2']}"
    assert lewat["satuan kosong"] == 1, lewat
    assert lewat["SKU kembar"] == 1, f"SKU kembar harus dilewat: {lewat}"

    # HPP tiap tingkat x isi harus sama dengan HPP grosir -- pengunci pemetaan kolom.
    assert abs(per["KLP-1"][4] * per["KLP-1"][3] - per["KLP-G"][4]) < 1, "pemetaan kolom HPP salah"

    print("semua uji harga_master LOLOS")


# --- Jaringan ---------------------------------------------------------------

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
MASTER_ID = "1BL34AALlM8tmJn7_z2L_RgTZVGEb4JsUVsnFVDzMyVM"
MASTER_TAB = "Master Pricelist New"
OUT_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def jalan():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)

    mentah = gc.open_by_key(MASTER_ID).worksheet(MASTER_TAB).get_all_values()
    print(f"Master {len(mentah)} baris", flush=True)

    baris, lewat = parse_harga(mentah)
    tanpa_hpp = sum(1 for b in baris if b[4] == "")
    tanpa_jual = sum(1 for b in baris if b[5] == "")
    print(f"{len(baris)} SKU berharga | tanpa HPP {tanpa_hpp} | tanpa harga jual {tanpa_jual}",
          flush=True)
    print("   dilewat:", ", ".join(f"{k} {v}" for k, v in lewat.items() if v), flush=True)

    sh = gc.open_by_key(OUT_ID)
    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < len(JUDUL) + 2:
            ws.resize(rows=max(ws.row_count, 8000), cols=len(JUDUL) + 2)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=8000, cols=len(JUDUL) + 2)

    stempel = time.strftime("%Y-%m-%d %H:%M:%S")
    ws.update(values=[JUDUL] + baris, range_name="A1")
    ws.format("A1:H1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    ws.update(values=[[f"Ditarik dari Master Pricelist {stempel} WIB — "
                       f"jalankan ulang scripts/harga_master.py sesudah master berubah"]],
              range_name="J1")
    print(f"Tab '{TAB}' ditulis ulang, {len(baris)} baris, stempel {stempel}", flush=True)
    for b in baris[:3]:
        print("   ", b, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="jalankan uji parsing, tanpa jaringan")
    args = ap.parse_args()
    if args.uji:
        uji()
        return 0

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan menulis sheet dengan parser yang rusak
    return jalan()


if __name__ == "__main__":
    sys.exit(main())
