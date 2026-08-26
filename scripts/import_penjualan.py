# -*- coding: utf-8 -*-
"""Tabel `penjualan_harian` (Supabase) -> tab 'Penjualan' dalam satuan dasar master.

    python3 -u import_penjualan.py            # tulis ulang tab Penjualan
    python3 -u import_penjualan.py --uji      # uji logika saja, tanpa jaringan

Alurnya:

    export POS -> upload lewat halaman admin -> penjualan_harian -> tab Penjualan
                                                                 -> sisa Area Display

Sebelum 2026-08-26 skrip ini membaca berkas .xlsx di laptop dan mencocokkan lewat
tab 'Peta Satuan Olsera'. Dua-duanya sudah tidak ada:

* Berkasnya sekarang diupload lewat aplikasi, dipotong jadi 9 kolom di browser,
  dan mendarat di tabel `penjualan_harian`.
* Pencocokan satuan TIDAK PERLU LAGI. Export "Item Penjualan berdasarkan Tanggal"
  membawa kolom `item sku`, dan SKU itu sudah menentukan produk SEKALIGUS
  satuannya (`PKG-0053-G` = Krtn, `-2` = Pack, `-3` = Pcs). Diukur pada export
  17-23 Agustus 2026: **668 dari 673 SKU langsung ketemu, 99,3%**, omzet tak
  tercakup Rp 103.400 dari Rp 107 juta.

  Export lama ("Qty Produk Terjual") tidak punya kolom itu, jadi dulu terpaksa
  dicocokkan lewat nama + satuan — dan di situlah ratusan baris terjemahan manual
  itu lahir. Masalahnya bukan katalog POS-nya, tapi jenis export yang dipilih.

Konversi ke satuan dasar diambil dari tabel `products` (kolom `mult`), sumber yang
sama dengan yang dipakai aplikasi waktu karyawan mengetik "1 Krtn + 2 Trs". Jadi
angka penjualan dan angka SO pasti memakai tangga satuan yang sama.

Baris yang GAGAL dicocokkan tetap ditulis dengan kolom Sebab terisi -- jangan
pernah dibuang diam-diam. Kalau dibuang, sisa display kelihatan lebih banyak
daripada kenyataan dan tidak ada yang tahu sebabnya. Di export contoh ada 39 baris
begitu senilai Rp 915.500 ("kertas nasi roll", "duo 40 hitam") -- itu barang yang
memang terjual tapi stoknya tidak dilacak siapa pun, jadi justru harus kelihatan.
"""
import argparse
import collections
import json
import os
import socket
import sys
import warnings
from pathlib import Path

TAB_JUAL = "Penjualan"

# Urutan kolom SENGAJA menaruh Produk di kolom 2 dan Qty Dasar di kolom 5, sama
# seperti susunan lama: `saldo_display.hitung_display()` menyebut kolom per nomor,
# jadi menggeser dua kolom itu diam-diam mengubah arti angka display.
JUDUL_JUAL = ["Tanggal", "SKU", "Produk", "Satuan", "Qty", "Qty Dasar",
              "Satuan Dasar", "Omzet", "Bayar", "Pelanggan", "Sebab"]

SEBAB_TANPA_SKU = "SKU kosong di POS — barang diketik manual, belum ada di master"
SEBAB_ASING = "SKU tidak ada di master — cek katalog POS"


# --- Bagian murni ----------------------------------------------------------

def susun(penjualan, produk):
    """Kembalikan (baris_tab, ringkas).

    penjualan : [{tanggal, sku, produk, qty, omzet, lunas, pelanggan}, ...]
    produk    : {sku: {"product_name", "variant", "mult"}}

    Digabung per (tanggal, sku, lunas, pelanggan). Bukan per nota: tab ini
    menjawab "berapa keluar hari itu" dan "siapa nunggak berapa", dan dua-duanya
    tidak butuh nomor nota. Nomor notanya tetap tersimpan di database kalau suatu
    saat perlu ditelusuri.
    """
    kel = collections.defaultdict(lambda: [0.0, 0.0])   # kunci -> [qty, omzet]
    nama_pos = {}
    for r in penjualan:
        sku = str(r.get("sku") or "").strip()
        tgl = str(r.get("tanggal") or "").strip()[:10]
        if not tgl:
            continue
        lunas = bool(r.get("lunas", True))
        pel = str(r.get("pelanggan") or "").strip()
        kunci = (tgl, sku, lunas, pel)
        kel[kunci][0] += float(r.get("qty") or 0)
        kel[kunci][1] += float(r.get("omzet") or 0)
        nama_pos.setdefault(kunci, str(r.get("produk") or "").strip())

    # Satuan dasar per produk = satuan yang mult-nya 1.
    dasar = {}
    for p in produk.values():
        if float(p.get("mult") or 0) == 1:
            dasar.setdefault(p["product_name"], p["variant"])

    baris = []
    ringkas = collections.Counter()
    for (tgl, sku, lunas, pel), (qty, omzet) in sorted(kel.items()):
        bayar = "Lunas" if lunas else "Tempo"
        p = produk.get(sku) if sku else None
        if not sku:
            baris.append([tgl, "", nama_pos[(tgl, sku, lunas, pel)], "", _rapi(qty),
                          "", "", _rapi(omzet), bayar, pel, SEBAB_TANPA_SKU])
            ringkas["tanpa_sku"] += 1
            ringkas["omzet_gagal"] += omzet
            continue
        if not p:
            baris.append([tgl, sku, nama_pos[(tgl, sku, lunas, pel)], "", _rapi(qty),
                          "", "", _rapi(omzet), bayar, pel, SEBAB_ASING])
            ringkas["sku_asing"] += 1
            ringkas["omzet_gagal"] += omzet
            continue
        mult = float(p.get("mult") or 1)
        nama = p["product_name"]
        baris.append([tgl, sku, nama, p.get("variant", ""), _rapi(qty),
                      _rapi(qty * mult), dasar.get(nama, ""), _rapi(omzet),
                      bayar, pel, ""])
        ringkas["cocok"] += 1
        ringkas["omzet_cocok"] += omzet
        if not lunas:
            ringkas["piutang"] += omzet
    ringkas["baris"] = len(baris)
    return baris, ringkas


def _rapi(x):
    """Bilangan bulat ditulis tanpa `.0` supaya sheet tidak penuh angka aneh."""
    f = float(x)
    return int(f) if f == int(f) else round(f, 4)


def uji():
    produk = {
        "PKG-0053-G": {"product_name": "Mika DP 7C", "variant": "Krtn (50 Pack)", "mult": 5000},
        "PKG-0053-2": {"product_name": "Mika DP 7C", "variant": "Pack (100 Pcs)", "mult": 100},
        "PKG-0053-3": {"product_name": "Mika DP 7C", "variant": "Pcs", "mult": 1},
        "PKG-0118-3": {"product_name": "Thinwall DM 200RB", "variant": "Trs", "mult": 1},
    }

    # 4 Pack = 400 Pcs. Ini inti seluruh skrip: qty POS dalam satuan varian,
    # sedangkan Log dan tab Stok memakai satuan dasar.
    b, _ = susun([{"tanggal": "2026-08-17", "sku": "PKG-0053-2", "produk": "Mika DP 7C - Pack",
                   "qty": 4, "omzet": 28000, "lunas": True, "pelanggan": ""}], produk)
    assert len(b) == 1, b
    assert b[0][5] == 400, f"konversi satuan salah: {b[0]}"
    assert b[0][6] == "Pcs", f"satuan dasar salah: {b[0]}"
    assert b[0][2] == "Mika DP 7C", f"nama harus dari master, bukan POS: {b[0]}"
    assert b[0][10] == "", f"harusnya tanpa sebab: {b[0]}"

    # Baris hari + SKU + status bayar yang sama digabung.
    b, r = susun([
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 2,
         "omzet": 21000, "lunas": True, "pelanggan": ""},
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 3,
         "omzet": 31500, "lunas": True, "pelanggan": ""},
    ], produk)
    assert len(b) == 1 and b[0][4] == 5 and b[0][7] == 52500, b

    # Tempo TIDAK digabung dengan lunas, walau produk dan tanggalnya sama --
    # kalau digabung, daftar piutang kehilangan angkanya.
    b, r = susun([
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 2,
         "omzet": 21000, "lunas": True, "pelanggan": ""},
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 1,
         "omzet": 10500, "lunas": False, "pelanggan": "MajaKoffie"},
    ], produk)
    assert len(b) == 2, b
    assert r["piutang"] == 10500, r
    tempo = [x for x in b if x[8] == "Tempo"][0]
    assert tempo[9] == "MajaKoffie", tempo

    # Dua pelanggan tempo berbeda tetap terpisah.
    b, r = susun([
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 1,
         "omzet": 10500, "lunas": False, "pelanggan": "MajaKoffie"},
        {"tanggal": "2026-08-17", "sku": "PKG-0118-3", "produk": "x", "qty": 1,
         "omzet": 10500, "lunas": False, "pelanggan": "Coffee Bawa"},
    ], produk)
    assert len(b) == 2 and r["piutang"] == 21000, (b, r)

    # SKU kosong: tetap ditulis, Qty Dasar dikosongkan, Sebab terisi. Nama yang
    # dipakai nama dari POS, karena master tidak punya barang ini.
    b, r = susun([{"tanggal": "2026-08-17", "sku": "", "produk": "kertas nasi roll",
                   "qty": 5, "omzet": 25000, "lunas": True, "pelanggan": ""}], produk)
    assert len(b) == 1 and b[0][5] == "" and b[0][10] == SEBAB_TANPA_SKU, b
    assert b[0][2] == "kertas nasi roll", b
    assert r["tanpa_sku"] == 1 and r["omzet_gagal"] == 25000, r

    # SKU yang tidak ada di master juga dilaporkan, bukan dibuang.
    b, r = susun([{"tanggal": "2026-08-17", "sku": "XXX-9999-3", "produk": "Barang Asing",
                   "qty": 1, "omzet": 5000, "lunas": True, "pelanggan": ""}], produk)
    assert b[0][10] == SEBAB_ASING and r["sku_asing"] == 1, (b, r)

    # Baris tanpa tanggal dilewat -- tanpa tanggal, penjualan tidak bisa
    # dibandingkan dengan waktu SO sama sekali.
    b, _ = susun([{"tanggal": "", "sku": "PKG-0118-3", "produk": "x", "qty": 1,
                   "omzet": 1, "lunas": True, "pelanggan": ""}], produk)
    assert b == [], b

    # Angka bulat tidak boleh berekor .0
    b, _ = susun([{"tanggal": "2026-08-17", "sku": "PKG-0053-G", "produk": "x", "qty": 1,
                   "omzet": 350000, "lunas": True, "pelanggan": ""}], produk)
    assert b[0][5] == 5000 and isinstance(b[0][5], int), b

    print("semua uji import_penjualan LOLOS", flush=True)


# --- Bagian jaringan -------------------------------------------------------

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", str(Path.home() / "Documents/Claude AI/claude-code-powershel-1427d99324cd.json"))
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def _cfg():
    """Kunci service_role: dari env dulu (dipakai GitHub Actions), lalu berkas lokal."""
    url = os.environ.get("SO_SUPABASE_URL", "https://qfqulgkpbjceizrapyom.supabase.co")
    key = os.environ.get("SO_SERVICE_KEY", "")
    if not key:
        berkas = Path(__file__).parent / "config.local.json"
        if not berkas.exists():
            raise SystemExit(
                "Butuh kunci service_role. Set env SO_SERVICE_KEY, atau isi "
                f"{berkas} seperti config.example.json.")
        cfg = json.loads(berkas.read_text())
        url, key = cfg["supabase_url"], cfg["service_role_key"]
    return url.rstrip("/"), key


def _ambil_semua(base, key, jalur, kolom, halaman=1000):
    """PostgREST membatasi jumlah baris per permintaan, jadi diambil berhalaman.

    Tanpa ini, tabel yang lebih besar dari batas akan terbaca SEBAGIAN tanpa galat
    apa pun -- dan penjualan yang hilang diam-diam bikin sisa display kelihatan
    lebih banyak daripada kenyataan.
    """
    import requests
    hasil = []
    mulai = 0
    while True:
        r = requests.get(
            f"{base}/rest/v1/{jalur}",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Range-Unit": "items", "Range": f"{mulai}-{mulai + halaman - 1}"},
            params={"select": kolom}, timeout=60)
        r.raise_for_status()
        potong = r.json()
        hasil.extend(potong)
        if len(potong) < halaman:
            return hasil
        mulai += halaman


def _tab(sh, judul, kolom, baris_awal=5000):
    import gspread
    try:
        return sh.worksheet(judul)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=judul, rows=baris_awal, cols=kolom)


def jalan():
    import gspread
    from google.oauth2.service_account import Credentials

    import requests

    base, key = _cfg()
    belum_migrasi = False
    try:
        jual = _ambil_semua(base, key, "penjualan_harian",
                            "tanggal,sku,produk,qty,omzet,lunas,pelanggan")
    except requests.HTTPError as e:
        # 404 di PostgREST = tabelnya belum ada. Bukan galat yang perlu menghentikan
        # apa pun: tab Penjualan tetap dibuat berisi baris judul saja, supaya formula
        # tab Ringkasan yang mengacu ke sini tidak terlanjur dipanggang jadi #REF!
        # oleh Google Sheets -- dan itu TIDAK sembuh sendiri waktu tabnya menyusul.
        if e.response is None or e.response.status_code != 404:
            raise
        belum_migrasi = True
        jual = []

    prod = _ambil_semua(base, key, "products", "sku,product_name,variant,mult")
    produk = {str(p["sku"]).strip(): p for p in prod if str(p.get("sku") or "").strip()}
    print(f"penjualan_harian {len(jual)} baris | products {len(produk)} SKU", flush=True)

    if belum_migrasi:
        print("Tabel `penjualan_harian` BELUM ADA — jalankan "
              "supabase/migration-penjualan.sql di SQL Editor dulu.", flush=True)
    elif not jual:
        print("Tabel penjualan_harian masih kosong — upload export POS lewat "
              "halaman admin.", flush=True)

    baris, ringkas = susun(jual, produk)
    tot = ringkas["cocok"] + ringkas["tanpa_sku"] + ringkas["sku_asing"]
    persen = (ringkas["cocok"] / tot * 100) if tot else 0
    if tot:
        print(f"{ringkas['cocok']}/{tot} baris cocok ({persen:.1f}%) | "
              f"tanpa SKU {ringkas['tanpa_sku']} | SKU asing {ringkas['sku_asing']}", flush=True)
        print(f"omzet cocok Rp {ringkas['omzet_cocok']:,.0f} | "
              f"tak tercakup Rp {ringkas['omzet_gagal']:,.0f} | "
              f"piutang Rp {ringkas['piutang']:,.0f}", flush=True)

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)
    ws = _tab(sh, TAB_JUAL, len(JUDUL_JUAL))
    ws.clear()
    ws.update(values=[JUDUL_JUAL] + baris, range_name="A1", value_input_option="RAW")
    ws.freeze(rows=1)
    print(f"Tab '{TAB_JUAL}' ditulis ulang, {len(baris)} baris.", flush=True)
    if not baris:
        print("   (baru baris judul — tab ini dibuat lebih dulu supaya formula tab "
              "lain tidak jadi #REF!)", flush=True)
    for b in baris[:3]:
        print("   ", b, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--uji", action="store_true", help="uji logika saja, tanpa jaringan")
    a = ap.parse_args()
    if a.uji:
        uji()
        return 0

    warnings.filterwarnings("ignore", message=".*gspread.*")
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    import google_ulang
    google_ulang.pasang()

    uji()   # pengaman: jangan menulis sheet dengan logika yang rusak
    return jalan()


if __name__ == "__main__":
    sys.exit(main())
