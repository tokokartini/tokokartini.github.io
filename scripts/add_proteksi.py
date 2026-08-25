# -*- coding: utf-8 -*-
"""Pasang peringatan pada sel formula supaya tidak hilang karena salah ketik.

    python3 -u add_proteksi.py            # pasang / perbarui proteksi
    python3 -u add_proteksi.py --daftar   # cuma tampilkan proteksi yang sekarang ada
    python3 -u add_proteksi.py --lepas    # lepas semua proteksi buatan skrip ini

Masalahnya nyata: tab Rekap, Template Olsera, Arsip Harian, Arsip Bulanan, Rekap
Mutasi, dan Kadaluarsa seluruhnya bergantung pada SATU formula di sel `A2`. Satu
orang mengetik di situ, formulanya hilang, tabnya kosong, dan tidak ada jejak
siapa pun yang tahu penyebabnya.

**Sengaja pakai `warning_only`, bukan kunci keras.** Kunci keras membatasi
penyuntingan ke daftar editor tertentu, dan itu berisiko mengunci Sopian sendiri
dari sheet miliknya atau menghalangi skrip yang memang harus menulis ke tab-tab
itu. Peringatan sudah cukup untuk bahaya yang sebenarnya — orang tidak sengaja
mengetik di sel yang salah — tanpa bisa membuat siapa pun terkunci.

`Rekap!G1` SENGAJA dibiarkan bebas: itu kotak tanggal yang memang harus diisi.
Tab Log tidak diproteksi selain baris judulnya; badan Log ditulis Edge Function
`upload-rak` dan tidak boleh ada apa pun yang menghalanginya.
"""
import argparse
import os
import socket
import sys
import warnings

PENANDA = "so-kartini otomatis"

# (nama tab, rentang, keterangan)
LINDUNGI = [
    ("Rekap", "A1:F1000", "hasil QUERY dari Log — kotak tanggal G1 sengaja dibiarkan bebas"),
    ("Template Olsera", "A1:G1000", "hasil QUERY dari Log untuk impor POS"),
    ("Arsip Harian", "A1:E5000", "hasil QUERY dari Log"),
    ("Arsip Bulanan", "A1:E2000", "hasil QUERY dari Log"),
    ("Rekap Mutasi", "A1:H5000", "hasil QUERY dari Mutasi"),
    ("Kadaluarsa", "A1:K5000", "hasil QUERY dari Log + kolom bantu"),
    ("Ringkasan", "A1:P60", "seluruhnya formula yang membaca tab lain"),
    ("Barang Rusak", "A1:N5000", "hasil QUERY dari Mutasi + kolom nilai"),
    ("Harga", "A1:H1", "judul; isinya ditulis scripts/harga_master.py"),
    ("Stok Gudang", "A1:M1", "judul; isinya ditulis scripts/hitung_saldo.py"),
    ("Stok Display", "A1:O1", "judul; isinya ditulis scripts/saldo_display.py"),
    ("Arsip Saldo", "A1:H1", "judul; isinya potret harian dari dua skrip saldo"),
    ("Selisih SO", "A1:K1", "judul; isinya ditulis scripts/selisih_so.py"),
    ("Log", "A1:I1", "baris judul saja — badan Log harus tetap bisa ditulis upload-rak"),
    ("Mutasi", "A1:L1", "baris judul saja — badan Mutasi ditulis upload-mutasi"),
]

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def proteksi_sekarang(sh):
    """Kembalikan daftar (id, judul tab, keterangan) dari proteksi yang terpasang."""
    meta = sh.fetch_sheet_metadata(
        {"fields": "sheets.properties.title,sheets.protectedRanges"})
    hasil = []
    for s in meta.get("sheets", []):
        judul = s["properties"]["title"]
        for p in s.get("protectedRanges", []) or []:
            hasil.append((p["protectedRangeId"], judul, p.get("description", "")))
    return hasil


def buang(sh, daftar):
    if not daftar:
        return 0
    sh.batch_update({"requests": [
        {"deleteProtectedRange": {"protectedRangeId": pid}} for pid, _, _ in daftar]})
    return len(daftar)


def jalan(mode):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    ada = proteksi_sekarang(sh)
    milik_skrip = [p for p in ada if PENANDA in p[2]]
    bukan_milik = [p for p in ada if PENANDA not in p[2]]

    print(f"Proteksi terpasang sekarang: {len(ada)} "
          f"({len(milik_skrip)} buatan skrip ini, {len(bukan_milik)} buatan orang)", flush=True)
    for _, judul, ket in ada:
        print(f"   {judul}: {ket[:70]}", flush=True)

    if mode == "daftar":
        return 0

    # Yang dipasang orang TIDAK disentuh — bisa saja sengaja dibuat Sopian.
    n = buang(sh, milik_skrip)
    if n:
        print(f"\n{n} proteksi lama buatan skrip dilepas dulu supaya tidak dobel", flush=True)
    if mode == "lepas":
        print("Selesai. Tidak ada proteksi baru dipasang.", flush=True)
        return 0

    punya = {w.title for w in sh.worksheets()}
    dipasang = lewat = 0
    for judul, rentang, ket in LINDUNGI:
        if judul not in punya:
            print(f"   lewat: tab '{judul}' belum ada", flush=True)
            lewat += 1
            continue
        sh.worksheet(judul).add_protected_range(
            rentang,
            description=f"{PENANDA} — {ket}",
            warning_only=True,
        )
        print(f"   {judul}!{rentang}", flush=True)
        dipasang += 1

    print(f"\n{dipasang} rentang diberi peringatan, {lewat} dilewat.", flush=True)
    print("Peringatan saja, bukan kunci: menyunting tetap bisa tapi Sheets bertanya dulu.",
          flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daftar", action="store_true", help="tampilkan proteksi yang ada, jangan ubah")
    ap.add_argument("--lepas", action="store_true", help="lepas proteksi buatan skrip ini")
    a = ap.parse_args()

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    return jalan("daftar" if a.daftar else "lepas" if a.lepas else "pasang")


if __name__ == "__main__":
    sys.exit(main())
