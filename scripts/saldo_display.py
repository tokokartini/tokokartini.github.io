# -*- coding: utf-8 -*-
"""Hitung sisa stok Area Display, tulis ke tab 'Stok Display'.

    python3 -u saldo_display.py            # baca sheet, tulis tab Stok Display
    python3 -u saldo_display.py --uji      # jalankan uji fungsi hitung, tanpa jaringan

Rumusnya:

    sisa display = hasil SO display + isi ulang masuk - mutasi keluar - penjualan

Bedanya dengan `hitung_saldo.py` (yang mengurus gudang): display berkurang tiap ada
yang laku, jadi angkanya butuh data penjualan Olsera lewat tab 'Penjualan'. Gudang
tidak butuh itu sama sekali karena POS cuma menjual dari display.

Sisa display BOLEH MINUS dan minus itu memang sinyal, bukan bug: berarti ada barang
yang laku tapi isi ulangnya tidak pernah dicatat di halaman Pengeluaran. Jangan
pernah dipaksa jadi 0.

Tiga hal yang sengaja dilaporkan terang-terangan, bukan disembunyikan:

1. Tab 'Penjualan' berisi RENTANG tanggal, bukan hari. Rentang yang melintasi hari
   SO (mulai sebelum SO, berakhir sesudahnya) TIDAK dihitung -- sebagiannya sudah
   tercermin di hasil hitungan fisik dan tidak ada cara memisahkan mana yang mana.
   Baris begitu diberi catatan supaya ketahuan angkanya belum lengkap.
2. Produk yang laku tapi belum pernah dihitung/dimutasi tetap muncul dengan hasil
   SO 0. Itu justru barang yang paling perlu dilihat.
3. Kalau Area Display belum pernah di-SO sama sekali, kolom Sisa dikosongkan.
   Tanpa titik awal, `isi ulang - penjualan` bukan sisa stok, cuma selisih -- dan
   angka besar bernilai minus di kolom Sisa gampang salah dibaca sebagai stok asli.

Hasilnya ditulis sebagai ANGKA BIASA, bukan formula, alasannya sama dengan
`hitung_saldo.py`: perbandingan waktu SO lawan waktu tiap mutasi tidak bisa
dikerjakan QUERY sheet tanpa jadi rumus raksasa yang tak bisa diuji. Jalankan ulang
skrip ini tiap kali mau angka terbaru.
"""
import argparse
import socket
import sys
import time
import warnings
from collections import defaultdict

DISPLAY = "Area Display"
TAB = "Stok Display"
JUDUL = ["Produk", "SKU", "Satuan", "Hasil SO", "Tgl SO",
         "Isi Ulang", "Keluar", "Terjual", "Sisa", "Catatan"]


# --- Bagian murni: bisa diuji tanpa jaringan -------------------------------

def hitung_display(log_rows, mutasi_rows, jual_rows):
    """Kembalikan (baris, peringatan).

    log_rows    : tab Log tanpa judul     -> [Waktu, Staff, Rak, Produk, Rincian, Qty, Satuan, ED, SKU]
    mutasi_rows : tab Mutasi tanpa judul  -> [Waktu, Staff, Jenis, Dari, Ke, Produk, Rincian, Qty, Satuan, SKU, Nota]
    jual_rows   : tab Penjualan tanpa judul -> [Awal, Akhir, Produk Master, Satuan Dasar, Qty Dasar]

    Kunci penggabungan adalah NAMA PRODUK, bukan SKU: tab Penjualan cuma punya nama
    (hasil pemetaan dari export Olsera lewat tab Peta Satuan Olsera). SKU tetap
    ikut ditampilkan kalau produknya pernah muncul di Log atau Mutasi.
    """
    # Waktu SO display terakhir. Timestamp penuh, sama seperti hitung_saldo.py.
    waktu_so = ""
    for r in log_rows:
        if _kolom(r, 2) == DISPLAY and _kolom(r, 0) > waktu_so:
            waktu_so = _kolom(r, 0)
    tgl_so = waktu_so[:10]

    baseline = defaultdict(float)
    masuk = defaultdict(float)
    keluar = defaultdict(float)
    terjual = defaultdict(float)
    sku = {}
    satuan = {}

    for r in log_rows:
        if _kolom(r, 2) != DISPLAY:
            continue
        produk = _kolom(r, 3)
        if not produk:
            continue
        sku.setdefault(produk, _kolom(r, 8))
        satuan.setdefault(produk, _kolom(r, 6))
        # Hanya hitungan dari hari SO terakhir yang jadi titik awal.
        if _kolom(r, 0)[:10] == tgl_so:
            baseline[produk] += _angka(_kolom(r, 5))

    for r in mutasi_rows:
        waktu, dari, ke, produk = _kolom(r, 0), _kolom(r, 3), _kolom(r, 4), _kolom(r, 5)
        if not produk or not waktu:
            continue
        if DISPLAY not in (dari, ke):
            continue
        sku.setdefault(produk, _kolom(r, 9))
        satuan.setdefault(produk, _kolom(r, 8))
        # Mutasi sebelum SO display sudah tercermin di hasil hitungan fisik.
        if waktu <= waktu_so:
            continue
        qty = _angka(_kolom(r, 7))
        if ke == DISPLAY:
            masuk[produk] += qty
        if dari == DISPLAY:
            keluar[produk] += qty

    # Penjualan: rentang tanggal, jadi butuh aturan lawan tanggal SO.
    lintas = set()
    for r in jual_rows:
        awal, akhir, produk = _kolom(r, 0), _kolom(r, 1), _kolom(r, 2)
        if not produk or not awal:
            continue
        satuan.setdefault(produk, _kolom(r, 3))
        if tgl_so:
            if akhir < tgl_so:
                continue                       # seluruhnya sebelum SO, sudah tercermin
            if awal <= tgl_so:
                lintas.add((awal, akhir))      # melintasi hari SO, tidak bisa dipisah
                continue
        terjual[produk] += _angka(_kolom(r, 4))

    produk_lintas = {_kolom(r, 2) for r in jual_rows
                     if (_kolom(r, 0), _kolom(r, 1)) in lintas and _kolom(r, 2)}

    baris = []
    for produk in sorted(set(baseline) | set(masuk) | set(keluar) | set(terjual)):
        awal_qty = baseline.get(produk, 0.0)
        m = masuk.get(produk, 0.0)
        k = keluar.get(produk, 0.0)
        j = terjual.get(produk, 0.0)

        catatan = []
        if not tgl_so:
            catatan.append("Area Display belum pernah di-SO")
        elif produk not in baseline:
            catatan.append("tidak ikut terhitung saat SO display")
        if produk in produk_lintas:
            catatan.append("ada penjualan di rentang yang melintasi hari SO, belum ikut dihitung")

        sisa = "" if not tgl_so else _rapi(awal_qty + m - k - j)
        baris.append([
            produk, sku.get(produk, ""), satuan.get(produk, ""),
            _rapi(awal_qty), tgl_so or "belum pernah SO",
            _rapi(m), _rapi(k), _rapi(j), sisa,
            "; ".join(catatan),
        ])

    peringatan = []
    if not tgl_so:
        peringatan.append(
            "Area Display belum pernah di-SO, jadi kolom Sisa dikosongkan. "
            "Hitung display dulu di aplikasi, baru angka sisa ada artinya.")
    for awal, akhir in sorted(lintas):
        peringatan.append(
            f"Penjualan {awal} s/d {akhir} melintasi hari SO ({tgl_so}), TIDAK dihitung. "
            "Sisa display untuk produk yang laku di rentang itu kelihatan lebih banyak "
            "daripada kenyataan.")
    return baris, peringatan


def _kolom(baris, i):
    return str(baris[i]).strip() if i < len(baris) and baris[i] is not None else ""


def _angka(teks):
    if not teks:
        return 0.0
    try:
        return float(str(teks).replace(".", "").replace(",", ".") if "," in str(teks) else teks)
    except ValueError:
        return 0.0


def _rapi(x):
    return int(x) if float(x).is_integer() else round(float(x), 3)


# --- Uji fungsi hitung ------------------------------------------------------

def uji():
    log = [
        # SO display lama, harus kalah oleh yang lebih baru
        ["2026-08-01 08:00:00", "rian", "Area Display", "Gula", "", "999", "Pack", "", "GLK"],
        ["2026-08-10 09:00:00", "rian", "Area Display", "Gula", "", "20", "Pack", "", "GLK"],
        ["2026-08-10 09:05:00", "rian", "Area Display", "Ceres", "", "5", "Pcs", "", "CRS"],
        # rak lain tidak boleh ikut sama sekali
        ["2026-08-20 09:00:00", "rian", "Gudang Ciherang", "Gula", "", "500", "Pack", "", "GLK"],
    ]
    mutasi = [
        # sebelum SO display -> tidak dihitung
        ["2026-08-09 07:00:00", "rian", "Isi Ulang", "Gudang Ciherang", "Area Display", "Gula", "", "9", "Pack", "GLK", ""],
        # sesudah SO -> dihitung
        ["2026-08-11 07:00:00", "rian", "Isi Ulang", "Gudang Ciherang", "Area Display", "Gula", "", "30", "Pack", "GLK", ""],
        # balik dari display ke gudang -> mengurangi
        ["2026-08-12 07:00:00", "rian", "Pindah", "Area Display", "Gudang Ciherang", "Gula", "", "4", "Pack", "GLK", ""],
        # mutasi antar gudang, display tidak terlibat -> abaikan
        ["2026-08-12 08:00:00", "rian", "Pindah", "Gudang Dapur Cherry", "Gudang Ciherang", "Ceres", "", "77", "Pcs", "CRS", ""],
    ]
    jual = [
        ["2026-06-15", "2026-06-21", "Gula", "Pack", "100"],      # seluruhnya sebelum SO -> abaikan
        ["2026-08-11", "2026-08-17", "Gula", "Pack", "12"],       # sesudah SO -> dihitung
        ["2026-08-11", "2026-08-17", "Kopi Saset", "Pcs", "8"],   # laku tapi tak pernah di-SO
    ]
    baris, peringatan = hitung_display(log, mutasi, jual)
    per = {b[0]: b for b in baris}

    gula = per["Gula"]
    assert gula[3] == 20, f"baseline SO display salah (SO lama ikut?): {gula}"
    assert gula[5] == 30, f"isi ulang salah (mutasi sebelum SO ikut?): {gula}"
    assert gula[6] == 4, f"keluar dari display salah: {gula}"
    assert gula[7] == 12, f"penjualan salah (periode sebelum SO ikut?): {gula}"
    assert gula[8] == 34, f"sisa salah: {gula}"        # 20 + 30 - 4 - 12
    assert gula[1] == "GLK", f"SKU hilang: {gula}"

    ceres = per["Ceres"]
    assert ceres[3] == 5 and ceres[8] == 5, f"mutasi antar gudang bocor ke display: {ceres}"

    kopi = per["Kopi Saset"]
    assert kopi[8] == -8, f"produk laku tanpa SO harus minus, bukan 0: {kopi}"
    assert "tidak ikut terhitung saat SO display" in kopi[9], f"catatan hilang: {kopi}"
    assert not peringatan, f"tidak ada rentang melintas, harusnya sunyi: {peringatan}"

    # Rentang yang melintasi hari SO tidak boleh ikut, tapi WAJIB dilaporkan.
    baris2, peringatan2 = hitung_display(
        log, mutasi, [["2026-08-08", "2026-08-14", "Gula", "Pack", "50"]])
    g2 = {b[0]: b for b in baris2}["Gula"]
    assert g2[7] == 0, f"rentang melintas tidak boleh dihitung: {g2}"
    assert "melintasi hari SO" in g2[9], f"catatan baris hilang: {g2}"
    assert peringatan2 and "melintasi hari SO" in peringatan2[0], peringatan2

    # Belum pernah SO display sama sekali -> kolom Sisa kosong, bukan angka minus besar.
    baris3, peringatan3 = hitung_display([], mutasi, jual)
    g3 = {b[0]: b for b in baris3}["Gula"]
    assert g3[8] == "", f"tanpa SO, Sisa harus kosong: {g3}"
    assert g3[4] == "belum pernah SO", g3
    assert g3[5] == 39, f"tanpa SO, semua isi ulang ikut: {g3}"    # 9 + 30
    assert peringatan3 and "belum pernah di-SO" in peringatan3[0], peringatan3

    print("semua uji hitung_display LOLOS")


# --- Bagian yang menyentuh jaringan ----------------------------------------

KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def tulis_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    log = sh.worksheet("Log").get_all_values()[1:]
    mutasi = sh.worksheet("Mutasi").get_all_values()[1:]
    try:
        jual = sh.worksheet("Penjualan").get_all_values()[1:]
    except gspread.exceptions.WorksheetNotFound:
        print("Tab 'Penjualan' belum ada. Jalankan dulu:\n"
              '  python3 -u import_penjualan.py "<export Olsera.xlsx>"', flush=True)
        return 1
    print(f"Log {len(log)} baris, Mutasi {len(mutasi)} baris, Penjualan {len(jual)} baris",
          flush=True)

    baris, peringatan = hitung_display(log, mutasi, jual)
    print(f"{len(baris)} produk di Area Display", flush=True)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < len(JUDUL) + 2:
            ws.resize(rows=max(ws.row_count, 20000), cols=len(JUDUL) + 2)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=20000, cols=len(JUDUL) + 2)

    stempel = time.strftime("%Y-%m-%d %H:%M:%S")
    ws.update(values=[JUDUL] + (baris or [["(belum ada data)"] + [""] * (len(JUDUL) - 1)]),
              range_name="A1")
    ws.format("A1:J1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)

    catatan = [f"Dihitung {stempel} WIB — jalankan ulang scripts/saldo_display.py untuk angka terbaru"]
    catatan += peringatan
    ws.update(values=[[c] for c in catatan], range_name="L1")

    print(f"Tab '{TAB}' ditulis ulang, {len(baris)} baris, stempel {stempel}", flush=True)
    for p in peringatan:
        print("  PERHATIAN:", p, flush=True)
    for b in baris[:5]:
        print("   ", b, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="jalankan uji fungsi hitung, tanpa jaringan")
    args = ap.parse_args()

    if args.uji:
        uji()
        return 0

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    # IPv6 ke Google menggantung di jaringan toko -- paksa IPv4.
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan pernah menulis sheet dengan logika yang rusak
    return tulis_sheet()


if __name__ == "__main__":
    sys.exit(main())
