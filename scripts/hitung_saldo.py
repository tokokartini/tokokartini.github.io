# -*- coding: utf-8 -*-
"""Hitung sisa stok per gudang. Hasilnya masuk tab 'Stok'.

    python3 -u hitung_saldo.py --uji      # jalankan uji fungsi hitung

Bukan skrip penulis sheet lagi — lihat hitung_stok.py.

Rumusnya:

    sisa = hasil SO terakhir + semua yang masuk sesudahnya - semua yang keluar

Angka gudang TIDAK butuh data penjualan Olsera sama sekali: barang cuma berkurang
dari gudang kalau ada orang memindahkannya, dan itu justru yang dicatat halaman
Pengeluaran. Beda dengan Area Display yang berkurang tiap ada yang laku -- display
sengaja tidak dihitung di sini, lihat catatan di docs/LANGKAH-MUTASI.md.

Hasilnya ditulis sebagai ANGKA BIASA, bukan formula: ini butuh membandingkan
waktu SO per lokasi dengan waktu tiap
mutasi, dan QUERY sheet tidak bisa melakukannya tanpa jadi rumus raksasa yang tak
bisa diuji. Jalankan ulang skrip ini tiap kali mau angka terbaru.
"""
import argparse
import sys
from collections import defaultdict

import harga_lookup
import sesi_so

# --- Bagian murni: bisa diuji tanpa jaringan -------------------------------

DISPLAY = "Area Display"
# Lokasi maya, bukan tempat yang punya stok. Harus dibuang dari daftar lokasi atau
# keduanya muncul sebagai "gudang" yang isinya menumpuk terus tanpa pernah keluar.
# Kembar dengan SUPPLIER dan BUANG di src/lib/mutasi.js.
MAYA = {"Barang Datang", "Barang Rusak"}


def hitung_saldo(log_rows, mutasi_rows, lokasi_aktif, harga_rows=()):
    """Kembalikan daftar baris Stok Gudang.

    log_rows    : baris tab Log tanpa judul  -> [Waktu, Staff, Rak, Produk, Rincian, Qty, Satuan, ED, SKU]
    mutasi_rows : baris tab Mutasi tanpa judul -> [Waktu, Staff, Jenis, Dari, Ke, Produk, Rincian, Qty, Satuan, SKU, Nota]
    lokasi_aktif: daftar nama lokasi dari tabel racks, Area Display sudah dibuang
    harga_rows  : baris tab Harga tanpa judul, untuk kolom HPP + Nilai Sisa.
                  Kosong = kedua kolom itu ikut kosong, sisanya tetap terhitung.

    Perbandingan waktu pakai timestamp penuh, bukan tanggal saja: mutasi yang
    terjadi beberapa jam SESUDAH rak itu dihitung harus ikut, sedangkan yang
    sebelumnya sudah termasuk dalam hasil hitungan dan tidak boleh dihitung dua kali.
    """
    # Waktu SO terakhir per lokasi + hasil hitungannya per SKU.
    waktu_so = {}
    tanggal_rak = defaultdict(set)
    for r in log_rows:
        waktu, rak = _kolom(r, 0), _kolom(r, 2)
        if not waktu or not rak:
            continue
        if waktu > waktu_so.get(rak, ""):
            waktu_so[rak] = waktu
        tanggal_rak[rak].add(waktu[:10])

    # Titik awalnya adalah SESI SO terakhir, bukan HARI terakhir: satu rak besar
    # sering dihitung dua hari bersambung, dan aturan lama membuang hari pertama.
    sesi_akhir = {rak: sesi_so.terakhir(tgl) for rak, tgl in tanggal_rak.items()}

    baseline = defaultdict(float)   # (lokasi, sku) -> qty saat SO
    nama = {}                       # sku -> (produk, satuan)
    for r in log_rows:
        waktu, rak, sku = _kolom(r, 0), _kolom(r, 2), _kolom(r, 8)
        if not sku or not rak or waktu[:10] not in sesi_akhir.get(rak, ()):
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

    per_sku, per_nama, _ = harga_lookup.muat_harga(harga_rows)

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
        sisa = _rapi(awal + m - k)
        hpp, _jual = harga_lookup.cari(per_sku, per_nama, sku, produk, satuan)
        baris.append([
            lokasi, sku, produk, satuan,
            _rapi(awal), tgl_so,
            _rapi(m), _rapi(k), sisa,
            "" if hpp is None else _rapi(hpp), harga_lookup.nilai(sisa, hpp),
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

    # SO yang memakan dua hari BERSAMBUNG itu satu sesi -- hari pertama tidak
    # boleh hilang. Ini yang dulu membuang 186 dari 326 baris Gudang Packaging.
    log_dua_hari = [
        ["2026-08-29 18:00:00", "dewo", "Gudang Packaging", "Mika", "", "600", "Pcs", "", "MKA"],
        ["2026-08-30 09:00:00", "dewo", "Gudang Packaging", "Sedotan", "", "40", "Pack", "", "SDT"],
        # produk sama, rak sama, hari sama, dua penghitung -> DIJUMLAH
        ["2026-08-30 10:00:00", "sofyan", "Gudang Packaging", "Sedotan", "", "10", "Pack", "", "SDT"],
    ]
    dua = {(b[0], b[1]): b for b in hitung_saldo(log_dua_hari, [], {"Gudang Packaging"})}
    assert dua[("Gudang Packaging", "MKA")][4] == 600, \
        f"hari pertama sesi ikut terhitung: {dua[('Gudang Packaging', 'MKA')]}"
    assert dua[("Gudang Packaging", "SDT")][4] == 50, \
        f"hitungan kembar di hari sama harus dijumlah: {dua[('Gudang Packaging', 'SDT')]}"


    # Tanpa tab Harga kolom HPP/Nilai kosong, tapi hitungan qty tetap jalan.
    assert gula[9] == "" and gula[10] == "", f"tanpa harga harus kosong: {gula}"

    harga = [
        ["GLK", "Gula", "Pack", 1, 12000, 15000, "HJ3", "Bahan Kue"],
        # Ceres dicari lewat nama+satuan karena SKU-nya beda di tab Harga
        ["CRS-LAIN", "Ceres", "Pcs", 1, 5000, 7000, "HJ3", "Bahan Kue"],
    ]
    dgn = {(b[0], b[1]): b for b in hitung_saldo(log, mutasi, lokasi, harga)}
    g = dgn[("Gudang Ciherang", "GLK")]
    assert g[9] == 12000, f"HPP lewat SKU gagal: {g}"
    assert g[10] == 255 * 12000, f"Nilai Sisa salah: {g}"
    c = dgn[("Gudang Ciherang", "CRS")]
    assert c[9] == 5000 and c[10] == 250000, f"HPP lewat nama+satuan gagal: {c}"
    m = dgn[("Gudang Packaging", "MKA")]
    assert m[9] == "" and m[10] == "", f"produk tanpa harga harus kosong, bukan 0: {m}"

    # Barang rusak = mutasi ke lokasi maya. Harus mengurangi gudang asalnya,
    # dan lokasi mayanya sendiri tidak boleh pernah punya baris saldo.
    rusak = mutasi + [["2026-08-13 09:00:00", "rian", "Rusak", "Gudang Ciherang",
                       "Barang Rusak", "Gula", "", "6", "Pack", "GLK", "", "Kadaluarsa"]]
    hasil_r = hitung_saldo(log, rusak, lokasi)
    gr = {(b[0], b[1]): b for b in hasil_r}[("Gudang Ciherang", "GLK")]
    assert gr[7] == 31, f"barang rusak harus menambah Keluar (25+6): {gr}"
    assert gr[8] == 249, f"sisa harus berkurang: {gr}"
    assert not any(b[0] == "Barang Rusak" for b in hasil_r), \
        "lokasi maya tidak boleh punya baris saldo"

    print("semua uji hitung_saldo LOLOS")


# --- Tidak lagi menulis sheet -----------------------------------------------
#
# Berkas ini sekarang MODUL MURNI. Yang menulis tab Stok adalah `hitung_stok.py`,
# yang memanggil fungsi hitung di atas untuk gudang lalu menggabungkannya dengan
# sisi satunya jadi satu tabel. Dulu tiap sisi punya tab dan skripnya sendiri, dan
# itu bisa setengah terbarui: satu sisi hari ini, satu sisi kemarin.

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uji", action="store_true", help="jalankan uji hitung, tanpa jaringan")
    ap.parse_args()
    uji()
    print("Modul murni — untuk menulis sheet jalankan: python3 -u hitung_stok.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
