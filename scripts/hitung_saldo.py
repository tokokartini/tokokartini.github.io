# -*- coding: utf-8 -*-
"""Hitung sisa stok per gudang, tulis ke tab 'Stok Gudang'.

    python3 -u hitung_saldo.py            # baca sheet, tulis tab Stok Gudang
    python3 -u hitung_saldo.py --uji      # jalankan uji fungsi hitung, tanpa jaringan

Rumusnya:

    sisa = hasil SO terakhir + semua yang masuk sesudahnya - semua yang keluar

Angka gudang TIDAK butuh data penjualan Olsera sama sekali: barang cuma berkurang
dari gudang kalau ada orang memindahkannya, dan itu justru yang dicatat halaman
Pengeluaran. Beda dengan Area Display yang berkurang tiap ada yang laku -- display
sengaja tidak dihitung di sini, lihat catatan di docs/LANGKAH-MUTASI.md.

Hasilnya ditulis sebagai ANGKA BIASA, bukan formula. Rekap per hari sudah dipegang
tab Rekap Mutasi; yang ini butuh membandingkan waktu SO per lokasi dengan waktu tiap
mutasi, dan QUERY sheet tidak bisa melakukannya tanpa jadi rumus raksasa yang tak
bisa diuji. Jalankan ulang skrip ini tiap kali mau angka terbaru.
"""
import argparse
import socket
import sys
import time
import warnings
from collections import defaultdict

# --- Bagian murni: bisa diuji tanpa jaringan -------------------------------

DISPLAY = "Area Display"


def hitung_saldo(log_rows, mutasi_rows, lokasi_aktif):
    """Kembalikan daftar baris Stok Gudang.

    log_rows    : baris tab Log tanpa judul  -> [Waktu, Staff, Rak, Produk, Rincian, Qty, Satuan, ED, SKU]
    mutasi_rows : baris tab Mutasi tanpa judul -> [Waktu, Staff, Jenis, Dari, Ke, Produk, Rincian, Qty, Satuan, SKU, Nota]
    lokasi_aktif: daftar nama lokasi dari tabel racks, Area Display sudah dibuang

    Perbandingan waktu pakai timestamp penuh, bukan tanggal saja: mutasi yang
    terjadi beberapa jam SESUDAH rak itu dihitung harus ikut, sedangkan yang
    sebelumnya sudah termasuk dalam hasil hitungan dan tidak boleh dihitung dua kali.
    """
    # Waktu SO terakhir per lokasi + hasil hitungannya per SKU.
    waktu_so = {}
    for r in log_rows:
        waktu, rak = _kolom(r, 0), _kolom(r, 2)
        if not waktu or not rak:
            continue
        if waktu > waktu_so.get(rak, ""):
            waktu_so[rak] = waktu

    baseline = defaultdict(float)   # (lokasi, sku) -> qty saat SO
    nama = {}                       # sku -> (produk, satuan)
    for r in log_rows:
        waktu, rak, sku = _kolom(r, 0), _kolom(r, 2), _kolom(r, 8)
        if not sku or not rak or waktu[:10] != waktu_so.get(rak, "")[:10]:
            continue
        baseline[(rak, sku)] += _angka(_kolom(r, 5))
        nama.setdefault(sku, (_kolom(r, 3), _kolom(r, 6)))

    masuk = defaultdict(float)
    keluar = defaultdict(float)
    for r in mutasi_rows:
        waktu, dari, ke, sku = _kolom(r, 0), _kolom(r, 3), _kolom(r, 4), _kolom(r, 9)
        if not sku or not waktu:
            continue
        qty = _angka(_kolom(r, 7))
        nama.setdefault(sku, (_kolom(r, 5), _kolom(r, 8)))
        # Mutasi sebelum SO lokasi itu sudah tercermin di hasil hitungan fisik.
        if ke in lokasi_aktif and waktu > waktu_so.get(ke, ""):
            masuk[(ke, sku)] += qty
        if dari in lokasi_aktif and waktu > waktu_so.get(dari, ""):
            keluar[(dari, sku)] += qty

    kunci = set(baseline) | set(masuk) | set(keluar)
    baris = []
    for lokasi, sku in sorted(kunci, key=lambda k: (k[0], nama.get(k[1], ("", ""))[0])):
        if lokasi not in lokasi_aktif:
            continue
        awal = baseline.get((lokasi, sku), 0.0)
        m, k = masuk.get((lokasi, sku), 0.0), keluar.get((lokasi, sku), 0.0)
        produk, satuan = nama.get(sku, ("", ""))
        # Potong ke tanggal HANYA kalau memang ada waktu SO -- kalau tidak, teks
        # "belum pernah SO" ikut terpotong jadi "belum pern".
        waktu = waktu_so.get(lokasi, "")
        tgl_so = waktu[:10] if waktu else "belum pernah SO"
        baris.append([
            lokasi, sku, produk, satuan,
            _rapi(awal), tgl_so,
            _rapi(m), _rapi(k), _rapi(awal + m - k),
        ])
    return baris


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
    lokasi = {"Gudang Ciherang", "Gudang Packaging"}
    log = [
        # SO lama, harus diabaikan karena ada SO yang lebih baru di rak yang sama
        ["2026-08-01 08:00:00", "rian", "Gudang Ciherang", "Gula", "", "999", "Pack", "", "GLK"],
        ["2026-08-10 09:00:00", "rian", "Gudang Ciherang", "Gula", "", "200", "Pack", "", "GLK"],
        ["2026-08-10 09:05:00", "rian", "Gudang Ciherang", "Ceres", "", "50", "Pcs", "", "CRS"],
    ]
    mutasi = [
        # sebelum SO -> tidak dihitung, sudah tercermin di hasil hitungan fisik
        ["2026-08-09 07:00:00", "rian", "Datang", "Barang Datang", "Gudang Ciherang", "Gula", "", "100", "Pack", "GLK", ""],
        # sesudah SO -> dihitung
        ["2026-08-11 07:00:00", "rian", "Datang", "Barang Datang", "Gudang Ciherang", "Gula", "", "80", "Pack", "GLK", ""],
        ["2026-08-12 10:00:00", "naruto", "Isi Ulang", "Gudang Ciherang", "Area Display", "Gula", "", "25", "Pack", "GLK", ""],
        # lokasi yang belum pernah SO: baseline 0, tetap muncul
        ["2026-08-12 11:00:00", "rian", "Datang", "Barang Datang", "Gudang Packaging", "Mika", "", "30", "Pcs", "MKA", ""],
    ]
    hasil = {(b[0], b[1]): b for b in hitung_saldo(log, mutasi, lokasi)}

    gula = hasil[("Gudang Ciherang", "GLK")]
    assert gula[4] == 200, f"baseline SO salah: {gula}"
    assert gula[6] == 80, f"masuk salah (mutasi sebelum SO ikut terhitung?): {gula}"
    assert gula[7] == 25, f"keluar salah: {gula}"
    assert gula[8] == 255, f"sisa salah: {gula}"

    ceres = hasil[("Gudang Ciherang", "CRS")]
    assert ceres[8] == 50, f"produk tanpa mutasi harus tetap muncul: {ceres}"

    mika = hasil[("Gudang Packaging", "MKA")]
    assert mika[4] == 0 and mika[5] == "belum pernah SO", f"lokasi tanpa SO salah: {mika}"
    assert mika[8] == 30, f"sisa lokasi tanpa SO salah: {mika}"

    assert not any(b[0] == DISPLAY for b in hitung_saldo(log, mutasi, lokasi)), "display tidak boleh ikut"
    print("semua uji hitung_saldo LOLOS")


# --- Bagian yang menyentuh jaringan ----------------------------------------

def tulis_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
    SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    log = sh.worksheet("Log").get_all_values()[1:]
    mutasi = sh.worksheet("Mutasi").get_all_values()[1:]
    print(f"Log {len(log)} baris, Mutasi {len(mutasi)} baris", flush=True)

    # Daftar lokasi diambil dari yang benar-benar muncul di data, bukan daftar tetap
    # di kode -- lokasi baru di tabel racks langsung ikut tanpa mengubah skrip.
    lokasi = {_kolom(r, 2) for r in log if _kolom(r, 2)}
    lokasi |= {_kolom(r, 3) for r in mutasi} | {_kolom(r, 4) for r in mutasi}
    lokasi -= {DISPLAY, "Barang Datang", ""}

    baris = hitung_saldo(log, mutasi, lokasi)
    print(f"{len(baris)} baris saldo di {len(lokasi)} lokasi", flush=True)

    judul = ["Lokasi", "SKU", "Produk", "Satuan", "Hasil SO", "Tgl SO", "Masuk", "Keluar", "Sisa"]
    # 11 kolom: 9 untuk tabel + kolom K untuk stempel waktu hitung.
    try:
        ws = sh.worksheet("Stok Gudang")
        ws.clear()
        if ws.col_count < 11:
            ws.resize(rows=max(ws.row_count, 20000), cols=11)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet("Stok Gudang", rows=20000, cols=11)

    stempel = time.strftime("%Y-%m-%d %H:%M:%S")
    ws.update(values=[judul] + (baris or [["(belum ada data)", "", "", "", "", "", "", "", ""]]),
              range_name="A1")
    ws.format("A1:I1", {"textFormat": {"bold": True}})
    ws.update(values=[[f"Dihitung {stempel} WIB — jalankan ulang scripts/hitung_saldo.py untuk angka terbaru"]],
              range_name="K1")
    print(f"Tab 'Stok Gudang' ditulis ulang, {len(baris)} baris, stempel {stempel}", flush=True)

    for b in baris[:5]:
        print("   ", b, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="jalankan uji fungsi hitung, tanpa jaringan")
    args = ap.parse_args()

    if args.uji:
        uji()
        return

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    # IPv6 ke Google menggantung di jaringan toko -- paksa IPv4.
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan pernah menulis sheet dengan logika yang rusak
    tulis_sheet()


if __name__ == "__main__":
    sys.exit(main())
