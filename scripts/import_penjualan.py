# -*- coding: utf-8 -*-
"""Ubah export Olsera 'Qty Produk Terjual' jadi tab 'Penjualan' (satuan dasar master).

    python3 -u import_penjualan.py "<file Qty Produk Terjual.xlsx>"
    python3 -u import_penjualan.py --uji

Alurnya:

    export Olsera  ->  Peta Satuan Olsera  ->  tab Penjualan  ->  saldo display

Yang TIDAK ketemu petanya masuk tab 'Penjualan Tak Cocok' lengkap dengan qty dan
omzetnya -- jangan pernah dibuang diam-diam. Kalau dibuang, saldo display kelihatan
lebih banyak daripada kenyataan, dan tidak ada yang tahu sebabnya.

Periode dibaca dari nama berkas Olsera, mis.
`Qty Produk Terjual-2026-06-15__2026-06-21.xlsx` -> 2026-06-15 s/d 2026-06-21.
Menjalankan ulang periode yang sama menimpa baris periode itu saja, periode lain
dibiarkan -- jadi aman diulang kalau export-nya diperbaiki.
"""
import argparse
import collections
import os
import re
import socket
import sys
import warnings

TAB_JUAL = "Penjualan"
TAB_GAGAL = "Penjualan Tak Cocok"
JUDUL_JUAL = ["Awal", "Akhir", "Produk Master", "Satuan Dasar", "Qty Dasar"]
JUDUL_GAGAL = ["Awal", "Akhir", "Produk Olsera", "Varian Olsera", "Qty Olsera", "Omzet", "Sebab"]


# --- Bagian murni ----------------------------------------------------------

def periode_dari_nama(nama):
    """`...-2026-06-15__2026-06-21.xlsx` -> ('2026-06-15', '2026-06-21')."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})__(\d{4}-\d{2}-\d{2})", str(nama))
    if not m:
        raise ValueError(
            f"tidak bisa membaca periode dari nama berkas: {nama!r}. "
            "Nama dari Olsera harusnya memuat `YYYY-MM-DD__YYYY-MM-DD`."
        )
    return m.group(1), m.group(2)


def konversi(penjualan, peta, awal, akhir):
    """Kembalikan (baris_penjualan, baris_gagal).

    peta : {(produk_olsera, varian_olsera): (produk_master, satuan_dasar, isi)}
           `isi` = berapa satuan dasar dalam satu satuan Olsera.
    """
    total = collections.defaultdict(float)
    satuan = {}
    gagal = []

    for r in penjualan:
        po, vo = str(r["product"]).strip(), str(r["variant"]).strip()
        qty = float(r.get("qty") or 0)
        kunci = peta.get((po, vo))

        if not kunci or kunci[2] in ("", None):
            gagal.append([awal, akhir, po, vo, _rapi(qty), _rapi(r.get("omzet", 0)),
                          "belum ada di Peta Satuan Olsera" if not kunci else "kolom Isi masih kosong"])
            continue

        produk_master, satuan_dasar, isi = kunci
        try:
            isi = float(str(isi).replace(",", "."))
        except ValueError:
            gagal.append([awal, akhir, po, vo, _rapi(qty), _rapi(r.get("omzet", 0)),
                          f"kolom Isi bukan angka: {isi!r}"])
            continue
        if isi <= 0:
            gagal.append([awal, akhir, po, vo, _rapi(qty), _rapi(r.get("omzet", 0)),
                          f"kolom Isi harus lebih dari 0, terbaca {isi}"])
            continue

        total[produk_master] += qty * isi
        satuan.setdefault(produk_master, satuan_dasar)

    baris = [[awal, akhir, p, satuan.get(p, ""), _rapi(q)] for p, q in sorted(total.items())]
    return baris, gagal


def _rapi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    return int(x) if x.is_integer() else round(x, 3)


# --- Uji --------------------------------------------------------------------

def uji():
    assert periode_dari_nama("Qty Produk Terjual-2026-06-15__2026-06-21.xlsx") == ("2026-06-15", "2026-06-21")
    try:
        periode_dari_nama("export.xlsx")
        raise AssertionError("nama tanpa periode harus ditolak")
    except ValueError:
        pass

    peta = {
        ("Fresh Milk Greenfields 1L", "Carton (12 Pcs)"): ("Fresh Milk Greenfields 1L", "Pcs", 12),
        ("Fresh Milk Greenfields 1L", "Pcs"): ("Fresh Milk Greenfields 1L", "Pcs", 1),
        ("Botol SKLB 250ml", "Carton (80pcs)"): ("Botol SKLB 250ml", "Pcs", ""),   # belum diisi
        ("Rusak", "Pcs"): ("Rusak", "Pcs", "abc"),
        ("Nol", "Pcs"): ("Nol", "Pcs", 0),
    }
    jual = [
        {"product": "Fresh Milk Greenfields 1L", "variant": "Carton (12 Pcs)", "qty": 9, "omzet": 100},
        {"product": "Fresh Milk Greenfields 1L", "variant": "Pcs", "qty": 4, "omzet": 20},
        {"product": "Botol SKLB 250ml", "variant": "Carton (80pcs)", "qty": 2, "omzet": 50},
        {"product": "Barang Asing", "variant": "Pcs", "qty": 7, "omzet": 30},
        {"product": "Rusak", "variant": "Pcs", "qty": 1, "omzet": 10},
        {"product": "Nol", "variant": "Pcs", "qty": 1, "omzet": 10},
    ]
    baris, gagal = konversi(jual, peta, "2026-06-15", "2026-06-21")

    per = {b[2]: b for b in baris}
    # 9 karton x 12 + 4 pcs = 112, DUA baris varian digabung jadi satu produk.
    assert per["Fresh Milk Greenfields 1L"][4] == 112, f"konversi satuan salah: {per}"
    assert per["Fresh Milk Greenfields 1L"][3] == "Pcs"
    assert len(baris) == 1, f"produk yang gagal tidak boleh ikut: {baris}"

    sebab = {g[2]: g[6] for g in gagal}
    assert sebab["Botol SKLB 250ml"] == "kolom Isi masih kosong", sebab
    assert sebab["Barang Asing"] == "belum ada di Peta Satuan Olsera", sebab
    assert "bukan angka" in sebab["Rusak"], sebab
    assert "lebih dari 0" in sebab["Nol"], sebab
    assert len(gagal) == 4, f"semua yang gagal harus dilaporkan: {gagal}"

    print("semua uji konversi LOLOS")


# --- Jaringan ---------------------------------------------------------------

KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def baca_export(path):
    import pandas as pd
    df = pd.read_excel(path)
    df = df[df["sales qty"].notna()]
    omzet = pd.to_numeric(df.get("subtotal sell price pos"), errors="coerce").fillna(0)
    qty = pd.to_numeric(df["sales qty"], errors="coerce").fillna(0)
    return [{"product": p, "variant": v, "qty": float(q), "omzet": float(o)}
            for p, v, q, o in zip(df["product"], df["variant"], qty, omzet)]


def _tab(sh, judul, kolom, baris_awal=5000):
    import gspread
    try:
        ws = sh.worksheet(judul)
        if ws.col_count < kolom:
            ws.resize(rows=max(ws.row_count, baris_awal), cols=kolom)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(judul, rows=baris_awal, cols=kolom)


def _tulis(ws, judul_kolom, baris_baru, awal, akhir):
    """Timpa hanya baris periode ini; periode lain dipertahankan."""
    lama = [r for r in ws.get_all_values()[1:] if r and (r[0], r[1]) != (awal, akhir)]
    ws.clear()
    ws.update(values=[judul_kolom] + lama + baris_baru, range_name="A1")
    ws.format("A1:" + chr(64 + len(judul_kolom)) + "1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    return len(lama)


def jalan(path):
    import gspread
    from google.oauth2.service_account import Credentials

    awal, akhir = periode_dari_nama(os.path.basename(path))
    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    try:
        peta_rows = sh.worksheet("Peta Satuan Olsera").get_all_values()[1:]
    except gspread.exceptions.WorksheetNotFound:
        print("Tab 'Peta Satuan Olsera' belum ada. Jalankan dulu:\n"
              f'  python3 -u peta_satuan.py "{path}"', flush=True)
        return 1

    peta = {}
    for r in peta_rows:
        if len(r) >= 5 and r[0].strip():
            peta[(r[0].strip(), r[1].strip())] = (r[2].strip() or r[0].strip(), r[3].strip(), r[4].strip())

    jual = baca_export(path)
    print(f"periode {awal} s/d {akhir} | export {len(jual)} baris | peta {len(peta)} baris", flush=True)

    baris, gagal = konversi(jual, peta, awal, akhir)

    lama = _tulis(_tab(sh, TAB_JUAL, 5), JUDUL_JUAL, baris, awal, akhir)
    _tulis(_tab(sh, TAB_GAGAL, 7), JUDUL_GAGAL, gagal, awal, akhir)

    omzet_gagal = sum(float(g[5] or 0) for g in gagal)
    omzet_total = sum(float(r["omzet"]) for r in jual)
    print(f"\nTab '{TAB_JUAL}' : {len(baris)} produk untuk periode ini "
          f"({lama} baris periode lain dipertahankan)", flush=True)
    print(f"Tab '{TAB_GAGAL}': {len(gagal)} baris "
          f"= {omzet_gagal/omzet_total*100:.1f}% dari omzet belum tercakup", flush=True)
    if gagal:
        print("\n5 yang paling berharga untuk dipetakan berikutnya:", flush=True)
        for g in sorted(gagal, key=lambda x: -float(x[5] or 0))[:5]:
            print(f"   Rp{float(g[5]):>12,.0f}  {g[2][:38]:38} | {g[3][:18]:18} | {g[6]}", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("berkas", nargs="?", help="file Qty Produk Terjual dari Olsera (.xlsx)")
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()

    if a.uji:
        uji()
        return 0
    if not a.berkas:
        ap.error("sebutkan file export Olsera, atau pakai --uji")

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan menulis sheet dengan logika yang rusak
    return jalan(a.berkas)


if __name__ == "__main__":
    sys.exit(main())
