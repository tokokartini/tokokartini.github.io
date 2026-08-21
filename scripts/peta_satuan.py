# -*- coding: utf-8 -*-
"""Bangun / perbarui tab 'Peta Satuan Olsera'.

    python3 -u peta_satuan.py "<file Qty Produk Terjual.xlsx>"
    python3 -u peta_satuan.py --uji

Kenapa tab ini perlu ada. Export Olsera memakai kosakata satuan sendiri yang tidak
sama dengan master toko:

    Olsera: Botol SKLB 250ml | Carton (80pcs)
    Master: Botol SKLB 250ml | Bal (100 Pcs)

Nama produknya sama persis, isi kartonnya beda -- 80 lawan 100. Menebak otomatis
berarti stok display salah 20% tanpa tanda apa pun, dan angka stok yang salah
diam-diam lebih berbahaya daripada tidak ada angka. Jadi yang tidak yakin TIDAK
PERNAH ditebak; dia masuk tab ini untuk diisi manusia.

Yang perlu diisi Sopian cuma kolom **Isi**: berapa satuan dasar master dalam satu
satuan Olsera. `Carton (12 Pcs)` -> 12. Satu angka, bukan mengetik ulang nama varian.

Baris diurutkan dari omzet terbesar, jadi mengisi 50 baris teratas saja sudah
menutup ~80% omzet. Isi dari atas, berhenti kapan saja.

Dijalankan ulang dengan file export baru: baris yang sudah kamu isi TIDAK
tertimpa, produk baru ditambahkan di bawah.
"""
import argparse
import collections
import json
import re
import socket
import sys
import urllib.parse
import urllib.request
import warnings

TAB = "Peta Satuan Olsera"
JUDUL = ["Produk Olsera", "Varian Olsera", "Produk Master", "Satuan Dasar Master",
         "Isi", "Status", "Omzet"]

OTOMATIS = "otomatis"
ISI_MANUAL = "isi kolom Isi"
TIDAK_ADA = "produk tidak ada di master"


# --- Bagian murni ----------------------------------------------------------

def norm_nama(s):
    """Samakan gaya penulisan: `1*11,34Kg` dan `1 x 11.34 Kg` jadi satu bentuk."""
    s = str(s or "").lower().replace("×", "x").replace("*", "x").replace(",", ".")
    return re.sub(r"[^a-z0-9.]", "", s)


def norm_varian(s):
    # "1 Ons" dan "Ons" satuan yang sama; Olsera kadang menulis angka 1 di depan.
    return re.sub(r"^1(?=[a-z])", "", norm_nama(s))


def indeks_master(produk):
    by_nv, by_name = {}, collections.defaultdict(list)
    for p in produk:
        by_nv.setdefault((norm_nama(p["product_name"]), norm_varian(p["variant"])), p)
        by_name[norm_nama(p["product_name"])].append(p)
    return by_nv, by_name


def satuan_dasar(daftar):
    """Satuan dengan mult 1; kalau tidak ada, mult terkecil. Sama seperti rows.ts."""
    if not daftar:
        return None
    return min(daftar, key=lambda p: (float(p["mult"]) != 1, float(p["mult"])))


def susun_peta(penjualan, produk, peta_lama=None):
    """Kembalikan (baris, ringkasan).

    penjualan : [{'product','variant','omzet'}]
    produk    : baris tabel products
    peta_lama : {(produk_olsera, varian_olsera): isi_yang_sudah_diisi_manusia}
    """
    peta_lama = peta_lama or {}
    by_nv, by_name = indeks_master(produk)

    baris = []
    ringkas = collections.Counter()
    for row in penjualan:
        po, vo = str(row["product"]).strip(), str(row["variant"]).strip()
        kunci = (po, vo)
        cocok = by_nv.get((norm_nama(po), norm_varian(vo)))
        senama = by_name.get(norm_nama(po))
        dasar = satuan_dasar(senama)

        if kunci in peta_lama and peta_lama[kunci] not in ("", None):
            # Isian manusia menang atas tebakan apa pun -- jangan pernah ditimpa.
            isi, status = peta_lama[kunci], "diisi manual"
        elif cocok:
            isi, status = _rapi(float(cocok["mult"])), OTOMATIS
        elif senama:
            isi, status = "", ISI_MANUAL
        else:
            isi, status = "", TIDAK_ADA

        ringkas[status] += 1
        baris.append([
            po, vo,
            (senama[0]["product_name"] if senama else ""),
            (dasar["variant"] if dasar else ""),
            isi, status, _rapi(row.get("omzet", 0)),
        ])

    # Yang butuh tangan manusia naik ke atas, diurutkan omzet terbesar, supaya
    # mengisi dari baris pertama langsung menutup porsi omzet terbesar.
    baris.sort(key=lambda b: (b[5] in (OTOMATIS, "diisi manual"), -float(b[6] or 0)))
    return baris, ringkas


def _rapi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    return int(x) if x.is_integer() else round(x, 4)


# --- Uji --------------------------------------------------------------------

def uji():
    produk = [
        {"sku": "A-G", "product_name": "Botol SKLB 250ml", "variant": "Bal (100 Pcs)", "mult": 100},
        {"sku": "A-1", "product_name": "Botol SKLB 250ml", "variant": "Pcs", "mult": 1},
        {"sku": "B-1", "product_name": "Almond Slice Blue Diamond 1*11,34Kg", "variant": "Ons", "mult": 1},
    ]
    jual = [
        {"product": "Botol SKLB 250ml", "variant": "Carton (80pcs)", "omzet": 500},
        {"product": "Botol SKLB 250ml", "variant": "Pcs", "omzet": 100},
        {"product": "Almond Slice Blue Diamond 1 x 11.34 Kg", "variant": "1 Ons", "omzet": 300},
        {"product": "Barang Asing", "variant": "Pcs", "omzet": 50},
    ]
    baris, ringkas = susun_peta(jual, produk)
    per_kunci = {(b[0], b[1]): b for b in baris}

    karton = per_kunci[("Botol SKLB 250ml", "Carton (80pcs)")]
    assert karton[4] == "" and karton[5] == ISI_MANUAL, f"carton 80 vs bal 100 TIDAK boleh ditebak: {karton}"
    assert karton[3] == "Pcs", f"satuan dasar master salah: {karton}"

    pcs = per_kunci[("Botol SKLB 250ml", "Pcs")]
    assert pcs[4] == 1 and pcs[5] == OTOMATIS, f"varian yang sama persis harus otomatis: {pcs}"

    almond = per_kunci[("Almond Slice Blue Diamond 1 x 11.34 Kg", "1 Ons")]
    assert almond[4] == 1 and almond[5] == OTOMATIS, f"normalisasi 1*11,34Kg gagal: {almond}"

    asing = per_kunci[("Barang Asing", "Pcs")]
    assert asing[5] == TIDAK_ADA and asing[2] == "", f"produk asing salah label: {asing}"

    # Baris yang butuh tangan manusia harus di atas, omzet terbesar dulu.
    assert baris[0][5] in (ISI_MANUAL, TIDAK_ADA), f"urutan salah, yang perlu diisi harus di atas: {baris[0]}"
    assert float(baris[0][6]) >= float(baris[1][6]), "belum urut omzet"

    # Isian manusia tidak boleh tertimpa saat dijalankan ulang.
    lagi, _ = susun_peta(jual, produk, {("Botol SKLB 250ml", "Carton (80pcs)"): 80})
    ulang = {(b[0], b[1]): b for b in lagi}[("Botol SKLB 250ml", "Carton (80pcs)")]
    assert ulang[4] == 80 and ulang[5] == "diisi manual", f"isian manual tertimpa: {ulang}"

    print("semua uji susun_peta LOLOS")


# --- Jaringan ---------------------------------------------------------------

KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def ambil_produk():
    cfg = json.load(open("/home/pianqt/Documents/Claude AI/so-kartini/scripts/config.local.json"))
    base, key = cfg["supabase_url"].rstrip("/"), cfg["service_role_key"]
    semua = []
    for off in range(0, 20000, 1000):
        url = f"{base}/rest/v1/products?" + urllib.parse.urlencode({
            "select": "sku,product_name,variant,mult", "active": "eq.true",
            "offset": str(off), "limit": "1000",
        })
        req = urllib.request.Request(url, headers={"apikey": key, "Authorization": "Bearer " + key})
        batch = json.load(urllib.request.urlopen(req, timeout=60))
        semua += batch
        if len(batch) < 1000:
            break
    return semua


def baca_export(path):
    import pandas as pd
    df = pd.read_excel(path)
    df = df[df["sales qty"].notna()]
    omzet = pd.to_numeric(df.get("subtotal sell price pos"), errors="coerce").fillna(0)
    return [{"product": p, "variant": v, "omzet": float(o)}
            for p, v, o in zip(df["product"], df["variant"], omzet)]


def jalan(path):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    jual = baca_export(path)
    produk = ambil_produk()
    print(f"export {len(jual)} baris, master {len(produk)} satuan produk", flush=True)

    # Pertahankan isian manusia dari jalannya yang lalu.
    peta_lama = {}
    try:
        lama = sh.worksheet(TAB).get_all_values()[1:]
        for r in lama:
            if len(r) >= 5 and r[4] not in ("", None) and len(r) >= 6 and r[5] == "diisi manual":
                peta_lama[(r[0].strip(), r[1].strip())] = r[4]
            elif len(r) >= 6 and r[4] not in ("", None) and r[5] == ISI_MANUAL:
                peta_lama[(r[0].strip(), r[1].strip())] = r[4]
        print(f"isian manual yang dipertahankan: {len(peta_lama)}", flush=True)
    except gspread.exceptions.WorksheetNotFound:
        pass

    baris, ringkas = susun_peta(jual, produk, peta_lama)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < 7:
            ws.resize(rows=max(ws.row_count, 5000), cols=7)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=5000, cols=7)

    ws.update(values=[JUDUL] + baris, range_name="A1")
    ws.format("A1:G1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)

    total = sum(float(b[6] or 0) for b in baris)
    perlu = [b for b in baris if b[5] in (ISI_MANUAL, TIDAK_ADA)]
    tertutup = total - sum(float(b[6] or 0) for b in perlu)
    print(f"\nTab '{TAB}' ditulis: {len(baris)} baris", flush=True)
    for status, n in ringkas.most_common():
        print(f"   {status:28} {n:4} baris", flush=True)
    print(f"\nomzet tercakup tanpa kerja manual: {tertutup/total*100:.1f}%", flush=True)

    kum = 0.0
    sisa = sum(float(b[6] or 0) for b in perlu)
    for n in (20, 50, 100, 150):
        kum = sum(float(b[6] or 0) for b in perlu[:n])
        print(f"   isi {n:3} baris teratas -> total tercakup {(tertutup+kum)/total*100:.1f}%", flush=True)


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
    jalan(a.berkas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
