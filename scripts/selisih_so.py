# -*- coding: utf-8 -*-
"""Bandingkan perkiraan stok lawan hitungan fisik tiap SO -> tab 'Selisih SO'.

    python3 -u selisih_so.py            # baca sheet, tulis tab Selisih SO
    python3 -u selisih_so.py --uji      # jalankan uji hitung, tanpa jaringan

Lubang yang ditutup: waktu SO, hitungan fisik MENGGANTIKAN angka sistem -- itu
memang gunanya SO. Tapi tanpa tab ini, berapa yang seharusnya ada tidak pernah
disimpan, jadi selisihnya hilang tanpa jejak. Barang yang menguap tidak ketahuan
kecuali sisanya sampai minus.

    perkiraan = hasil SO sebelumnya + masuk - keluar (di antara dua SO itu)
    selisih   = hasil hitung sekarang - perkiraan

Selisih MINUS = barang kurang dari yang seharusnya (menguap). Selisih PLUS =
barang lebih banyak dari catatan, biasanya tanda ada barang masuk yang lupa
dicatat.

## Dua hal yang sengaja dibedakan

1. **Lokasi yang sudah pernah di-SO** punya titik awal sungguhan, jadi selisihnya
   bisa dipercaya. Kolom Dasar menyebut tanggal SO pembandingnya.
2. **Lokasi yang BARU PERTAMA di-SO** tidak punya titik awal. Perkiraannya cuma
   dari mutasi yang tercatat, jadi kalau gudang itu sudah punya stok lama yang tak
   pernah dicatat, angkanya salah besar. Baris begitu tetap ditampilkan -- tapi
   kolom Dasar menyebutnya terang-terangan, jangan disamakan dengan selisih nyata.

Baris yang selisihnya 0 tidak ditulis: yang cocok bukan pekerjaan. Jumlahnya tetap
dilaporkan di stempel supaya ketahuan bedanya "semua cocok" dengan "belum jalan".
"""
import argparse
import os
import socket
import sys
import time
import warnings
from collections import defaultdict

import harga_lookup

TAB = "Selisih SO"
JUDUL = ["Tgl SO", "Lokasi", "SKU", "Produk", "Satuan", "Perkiraan", "Hasil Hitung",
         "Selisih", "HPP", "Nilai Selisih", "Dasar"]


# --- Bagian murni ----------------------------------------------------------

def hitung_selisih(log_rows, mutasi_rows, harga_rows=()):
    """Kembalikan (baris, cocok) — baris selisih bukan-nol, dan berapa yang cocok."""
    # Kelompokkan SO per lokasi lalu per tanggal. Satu SO = satu tanggal di satu rak;
    # waktu penuh dipakai untuk memotong jendela mutasi.
    so = defaultdict(lambda: defaultdict(lambda: {"qty": defaultdict(float), "akhir": ""}))
    nama, satuan = {}, {}
    for r in log_rows:
        waktu, rak, sku = _k(r, 0), _k(r, 2), _k(r, 8)
        if not waktu or not rak or not sku:
            continue
        hari = so[rak][waktu[:10]]
        hari["qty"][sku] += _n(_k(r, 5))
        if waktu > hari["akhir"]:
            hari["akhir"] = waktu
        nama.setdefault(sku, _k(r, 3))
        satuan.setdefault(sku, _k(r, 6))

    # Mutasi dikelompokkan per lokasi, disimpan dengan waktunya supaya bisa disaring
    # per jendela antar-SO.
    masuk = defaultdict(list)
    keluar = defaultdict(list)
    for r in mutasi_rows:
        waktu, dari, ke, sku = _k(r, 0), _k(r, 3), _k(r, 4), _k(r, 9)
        if not waktu or not sku:
            continue
        qty = _n(_k(r, 7))
        nama.setdefault(sku, _k(r, 5))
        satuan.setdefault(sku, _k(r, 8))
        if ke:
            masuk[ke].append((waktu, sku, qty))
        if dari:
            keluar[dari].append((waktu, sku, qty))

    per_sku, per_nama, _ = harga_lookup.muat_harga(harga_rows)

    baris, cocok = [], 0
    for lokasi in sorted(so):
        tanggal = sorted(so[lokasi])
        for i, tgl in enumerate(tanggal):
            ini = so[lokasi][tgl]
            sebelum = so[lokasi][tanggal[i - 1]] if i else None
            batas_bawah = sebelum["akhir"] if sebelum else ""
            batas_atas = ini["akhir"]
            dasar = (f"SO {tanggal[i - 1]}" if sebelum
                     else "SO pertama — perkiraan dari mutasi saja, belum tentu benar")

            geser = defaultdict(float)
            for waktu, sku, qty in masuk[lokasi]:
                if batas_bawah < waktu <= batas_atas:
                    geser[sku] += qty
            for waktu, sku, qty in keluar[lokasi]:
                if batas_bawah < waktu <= batas_atas:
                    geser[sku] -= qty

            awal = sebelum["qty"] if sebelum else {}
            # Produk yang DIHARAPKAN ada tapi tidak ikut dihitung juga harus muncul:
            # hasilnya 0 dan itu justru selisih terbesar.
            skus = set(awal) | set(geser) | set(ini["qty"])
            for sku in sorted(skus, key=lambda s: nama.get(s, s)):
                perkiraan = awal.get(sku, 0.0) + geser.get(sku, 0.0)
                hasil = ini["qty"].get(sku, 0.0)
                selisih = hasil - perkiraan
                if abs(selisih) < 1e-9:
                    cocok += 1
                    continue
                hpp, _j = harga_lookup.cari(per_sku, per_nama, sku,
                                            nama.get(sku, ""), satuan.get(sku, ""))
                baris.append([
                    tgl, lokasi, sku, nama.get(sku, ""), satuan.get(sku, ""),
                    _r(perkiraan), _r(hasil), _r(selisih),
                    "" if hpp is None else _r(hpp), harga_lookup.nilai(_r(selisih), hpp),
                    dasar,
                ])
    # Terbaru di atas, lalu selisih paling mahal dulu.
    baris.sort(key=lambda b: (b[0], -abs(float(b[9]) if b[9] != "" else 0)), reverse=False)
    baris.sort(key=lambda b: b[0], reverse=True)
    return baris, cocok


def _k(baris, i):
    return str(baris[i]).strip() if i < len(baris) and baris[i] is not None else ""


def _n(t):
    if not t:
        return 0.0
    try:
        return float(str(t).replace(".", "").replace(",", ".") if "," in str(t) else t)
    except ValueError:
        return 0.0


def _r(x):
    return int(x) if float(x).is_integer() else round(float(x), 3)


# --- Uji --------------------------------------------------------------------

def uji():
    harga = [["GLK", "Gula", "Pack", 1, 12000, 15000, "HJ3", "X"],
             ["CRS", "Ceres", "Pcs", 1, 500, 800, "HJ3", "X"]]

    # SO pertama: tidak ada pembanding, perkiraan cuma dari mutasi.
    log1 = [["2026-08-25 15:00:52", "rian", "Area Display", "Gula", "", "19", "Pack", "", "GLK"]]
    mut1 = [
        ["2026-08-25 15:00:02", "rian", "Isi Ulang", "Gudang A", "Area Display", "Gula", "", "22", "Pack", "GLK", "", ""],
        ["2026-08-25 15:00:23", "rian", "Rusak", "Area Display", "Barang Rusak", "Gula", "", "1", "Pack", "GLK", "", "Rusak / pecah"],
    ]
    b, cocok = hitung_selisih(log1, mut1, harga)
    assert len(b) == 1, f"harusnya 1 baris selisih: {b}"
    assert b[0][5] == 21, f"perkiraan 0+22-1 salah: {b[0]}"
    assert b[0][6] == 19, b[0]
    assert b[0][7] == -2, f"selisih harus -2: {b[0]}"
    assert b[0][9] == -24000, f"nilai selisih salah: {b[0]}"
    assert "SO pertama" in b[0][10], f"dasar harus ditandai: {b[0]}"
    assert cocok == 0

    # SO kedua: pembandingnya SO pertama, mutasi SEBELUM SO pertama tidak boleh ikut.
    log2 = log1 + [
        ["2026-08-27 09:00:00", "rian", "Area Display", "Gula", "", "30", "Pack", "", "GLK"],
        ["2026-08-27 09:01:00", "rian", "Area Display", "Ceres", "", "5", "Pcs", "", "CRS"],
    ]
    mut2 = mut1 + [
        ["2026-08-26 08:00:00", "rian", "Isi Ulang", "Gudang A", "Area Display", "Gula", "", "15", "Pack", "GLK", "", ""],
    ]
    b2, cocok2 = hitung_selisih(log2, mut2, harga)
    per = {(x[0], x[2]): x for x in b2}
    g = per[("2026-08-27", "GLK")]
    assert g[5] == 34, f"perkiraan 19+15 salah (mutasi sebelum SO pertama ikut?): {g}"
    assert g[7] == -4, f"selisih salah: {g}"
    assert g[10] == "SO 2026-08-25", f"dasar salah: {g}"
    # Ceres baru muncul di SO kedua: perkiraan 0, hasil 5 -> selisih +5.
    c = per[("2026-08-27", "CRS")]
    assert c[5] == 0 and c[7] == 5, f"produk baru salah: {c}"

    # Produk yang diharapkan ada tapi tidak dihitung sama sekali.
    log3 = log1 + [["2026-08-27 09:00:00", "rian", "Area Display", "Ceres", "", "5", "Pcs", "", "CRS"]]
    b3, _ = hitung_selisih(log3, mut1, harga)
    hilang = [x for x in b3 if x[0] == "2026-08-27" and x[2] == "GLK"][0]
    assert hilang[5] == 19 and hilang[6] == 0 and hilang[7] == -19, \
        f"produk tak terhitung harus muncul: {hilang}"

    # Yang cocok tidak ditulis, tapi dihitung.
    log4 = log1 + [["2026-08-27 09:00:00", "rian", "Area Display", "Gula", "", "19", "Pack", "", "GLK"]]
    b4, cocok4 = hitung_selisih(log4, mut1, harga)
    assert not [x for x in b4 if x[0] == "2026-08-27"], f"yang cocok tidak boleh ditulis: {b4}"
    assert cocok4 == 1, cocok4

    # Rak lain tidak boleh saling mempengaruhi.
    log5 = log1 + [["2026-08-25 16:00:00", "rian", "Gudang A", "Gula", "", "100", "Pack", "", "GLK"]]
    b5, _ = hitung_selisih(log5, mut1, harga)
    ga = [x for x in b5 if x[1] == "Gudang A"][0]
    # Gudang A mengirim 22 keluar sebelum SO-nya -> perkiraan -22, dihitung 100.
    assert ga[5] == -22 and ga[7] == 122, f"lokasi tercampur: {ga}"

    print("semua uji selisih_so LOLOS")


# --- Jaringan ---------------------------------------------------------------

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def tulis_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    log = sh.worksheet("Log").get_all_values()[1:]
    mutasi = sh.worksheet("Mutasi").get_all_values()[1:]
    try:
        harga = sh.worksheet("Harga").get_all_values()[1:]
    except gspread.exceptions.WorksheetNotFound:
        harga = []
    print(f"Log {len(log)} baris, Mutasi {len(mutasi)} baris, Harga {len(harga)} baris",
          flush=True)

    baris, cocok = hitung_selisih(log, mutasi, harga)
    print(f"{len(baris)} baris selisih, {cocok} produk cocok", flush=True)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < len(JUDUL) + 2:
            ws.resize(rows=max(ws.row_count, 20000), cols=len(JUDUL) + 2)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=20000, cols=len(JUDUL) + 2)

    stempel = time.strftime("%Y-%m-%d %H:%M:%S")
    ws.update(values=[JUDUL] + (baris or [["(semua cocok)"] + [""] * (len(JUDUL) - 1)]),
              range_name="A1")
    ws.format("A1:K1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)

    kurang = sum(b[9] for b in baris if b[9] != "" and b[9] < 0)
    lebih = sum(b[9] for b in baris if b[9] != "" and b[9] > 0)
    ws.update(values=[
        [f"Dihitung {stempel} WIB — jalankan ulang scripts/selisih_so.py untuk angka terbaru"],
        [f"{cocok} produk cocok, {len(baris)} selisih"],
        [f"Nilai barang kurang Rp {abs(kurang):,.0f}".replace(",", ".")],
        [f"Nilai barang lebih Rp {lebih:,.0f}".replace(",", ".")],
    ], range_name="M1")

    print(f"Tab '{TAB}' ditulis ulang, stempel {stempel}", flush=True)
    print(f"   kurang Rp {abs(kurang):,.0f} | lebih Rp {lebih:,.0f}", flush=True)
    for b in baris[:5]:
        print("   ", b, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="jalankan uji hitung, tanpa jaringan")
    a = ap.parse_args()
    if a.uji:
        uji()
        return 0
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    uji()  # pengaman: jangan menulis sheet dengan logika yang rusak
    return tulis_sheet()


if __name__ == "__main__":
    sys.exit(main())
