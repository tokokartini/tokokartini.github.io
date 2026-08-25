# -*- coding: utf-8 -*-
"""Buang data simulasi SO pada satu tanggal, dari sheet DAN dari database.

    python3 -u bersihkan_simulasi.py 2026-08-26            # lihat saja, tidak menghapus
    python3 -u bersihkan_simulasi.py 2026-08-26 --tulis    # hapus beneran

Dipakai sesudah latihan SO, supaya angka latihan tidak ikut terhitung waktu SO
asli. Entri yang sudah ter-upload TIDAK bisa dihapus lewat aplikasi (dijaga RLS),
jadi harus lewat sini.

Yang dihapus, semuanya HANYA yang waktunya jatuh pada tanggal yang disebut:

- baris tab **Log** dan tab **Mutasi**
- baris tabel `count_entries` dan `movements` di Supabase

Tab olahan (Arsip Harian, Kadaluarsa, Barang Rusak, Ringkasan) tidak perlu
disentuh — semuanya formula di atas Log dan Mutasi, jadi ikut bersih sendiri. Tab
Stok dan Selisih SO ditulis ulang waktu skripnya dijalankan lagi.

## Dua pengaman

1. **Batal kalau masih ada entri yang belum di-upload** (`uploaded_at IS NULL`).
   Itu tandanya ada orang yang sedang menghitung. Menghapus baris Log saat upload
   mendarat pernah menghilangkan data permanen (7 entri, 2026-07-30).
2. **Baris Log dihapus per baris pakai `deleteDimension`, bukan dengan menulis
   ulang seluruh tab.** Penulisan ulang itu persis yang dulu menimpa enam batch
   upload sekaligus.

Bawaannya cuma melihat. Tidak ada yang terhapus tanpa `--tulis`.
"""
import argparse
import json
import os
import re
import socket
import sys
import warnings
from pathlib import Path

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def baris_tanggal(rows, tanggal):
    """Nomor baris sheet (1-based, sudah termasuk baris judul) yang waktunya = tanggal."""
    return [i for i, r in enumerate(rows[1:], start=2)
            if r and str(r[0]).strip().startswith(tanggal)]


def db(cfg, metode, jalur, **kw):
    import requests
    key = cfg["service_role_key"]
    return requests.request(
        metode, f"{cfg['supabase_url'].rstrip('/')}/rest/v1/{jalur}",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "count=exact"},
        timeout=30, **kw)


def jalan(tanggal, tulis):
    import gspread
    from google.oauth2.service_account import Credentials

    cfg = json.loads((Path(__file__).parent / "config.local.json").read_text())

    # --- pengaman 1: tidak boleh ada SO yang sedang berjalan ---
    r = db(cfg, "GET", "count_entries?uploaded_at=is.null&select=id&limit=1")
    r.raise_for_status()
    terbuka = int(r.headers.get("content-range", "*/0").split("/")[-1])
    if terbuka:
        print(f"BATAL: masih ada {terbuka} entri yang belum di-upload — ada yang sedang "
              f"menghitung.\nTunggu semua rak ter-upload dulu, baru bersihkan.", flush=True)
        return 1
    print("Tidak ada entri terbuka. Aman diteruskan.", flush=True)

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    rencana = []
    for nama in ("Log", "Mutasi"):
        ws = sh.worksheet(nama)
        rows = ws.get_all_values()
        nomor = baris_tanggal(rows, tanggal)
        rencana.append((ws, nama, rows, nomor))
        print(f"\nTab {nama}: {len(rows) - 1} baris, {len(nomor)} kena tanggal {tanggal}",
              flush=True)
        for i in nomor[:5]:
            print(f"   baris {i}: {rows[i - 1][:6]}", flush=True)
        if len(nomor) > 5:
            print(f"   ... dan {len(nomor) - 5} baris lagi", flush=True)

    hitung = {}
    for tabel, kolom in (("count_entries", "created_at"), ("movements", "created_at")):
        r = db(cfg, "GET", f"{tabel}?{kolom}=gte.{tanggal}T00:00:00"
                           f"&{kolom}=lt.{tanggal}T23:59:59.999&select=id&limit=1")
        if r.status_code >= 400:
            print(f"\nTabel {tabel}: tidak terbaca ({r.status_code}) — dilewat", flush=True)
            continue
        n = int(r.headers.get("content-range", "*/0").split("/")[-1])
        hitung[(tabel, kolom)] = n
        print(f"\nTabel {tabel}: {n} baris kena tanggal {tanggal}", flush=True)

    total = sum(len(n) for _, _, _, n in rencana) + sum(hitung.values())
    if not total:
        print(f"\nTidak ada apa pun bertanggal {tanggal}. Tidak ada yang dihapus.", flush=True)
        return 0

    if not tulis:
        print(f"\n--- LIHAT SAJA --- {total} baris akan dihapus.\n"
              f"Ulangi dengan --tulis kalau memang mau dihapus.", flush=True)
        return 0

    # --- hapus baris sheet dari BAWAH ke atas supaya nomor baris di atasnya tidak bergeser ---
    for ws, nama, _, nomor in rencana:
        if not nomor:
            continue
        permintaan = [{"deleteDimension": {"range": {
            "sheetId": ws.id, "dimension": "ROWS",
            "startIndex": i - 1, "endIndex": i}}} for i in sorted(nomor, reverse=True)]
        sh.batch_update({"requests": permintaan})
        print(f"Tab {nama}: {len(nomor)} baris dihapus", flush=True)

    for (tabel, kolom), n in hitung.items():
        if not n:
            continue
        r = db(cfg, "DELETE", f"{tabel}?{kolom}=gte.{tanggal}T00:00:00"
                              f"&{kolom}=lt.{tanggal}T23:59:59.999")
        if r.status_code >= 400:
            print(f"Tabel {tabel}: GAGAL dihapus ({r.status_code}) {r.text[:200]}", flush=True)
        else:
            print(f"Tabel {tabel}: {n} baris dihapus", flush=True)

    print("\nSelesai. Jalankan ulang skrip stok supaya tab Stok dan Selisih SO\n"
          "ikut bersih:\n"
          "   python3 -u hitung_stok.py && python3 -u selisih_so.py", flush=True)
    return 0


def uji():
    rows = [["Waktu", "Staff"],
            ["2026-08-26 09:00:00", "rian"],
            ["2026-08-27 09:00:00", "rian"],
            ["2026-08-26 23:59:00", "dewo"],
            [], ["", ""]]
    assert baris_tanggal(rows, "2026-08-26") == [2, 4], baris_tanggal(rows, "2026-08-26")
    assert baris_tanggal(rows, "2026-08-27") == [3]
    assert baris_tanggal(rows, "2026-08-28") == []
    # Baris judul tidak boleh pernah ikut.
    assert 1 not in baris_tanggal(rows, "Waktu")
    print("uji baris_tanggal LOLOS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tanggal", nargs="?", help="tanggal simulasi, bentuk YYYY-MM-DD")
    ap.add_argument("--tulis", action="store_true", help="hapus beneran (bawaan: lihat saja)")
    ap.add_argument("--uji", action="store_true", help="uji fungsi murni, tanpa jaringan")
    a = ap.parse_args()

    if a.uji:
        uji()
        return 0
    if not a.tanggal or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.tanggal):
        ap.error("sebutkan tanggal bentuk YYYY-MM-DD, mis. 2026-08-26")

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan pernah menghapus dengan logika pemilihan baris yang rusak
    return jalan(a.tanggal, a.tulis)


if __name__ == "__main__":
    sys.exit(main())
