# -*- coding: utf-8 -*-
"""Hitung sisa stok Area Display. Hasilnya masuk tab 'Stok'.

    python3 -u saldo_display.py --uji      # jalankan uji fungsi hitung

Bukan skrip penulis sheet lagi — lihat hitung_stok.py.

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
import sys
from collections import defaultdict

import harga_lookup
import sesi_so

KOL_SEBAB = 10   # tab Penjualan: kolom Sebab. Terisi = gagal dikonversi.
DISPLAY = "Area Display"
JUDUL = ["Produk", "SKU", "Satuan", "Hasil SO", "Tgl SO",
         "Isi Ulang", "Keluar", "Terjual", "Sisa",
         "HPP", "Nilai Sisa", "Nilai Terjual (HPP)", "Catatan"]


# --- Bagian murni: bisa diuji tanpa jaringan -------------------------------

def hitung_display(log_rows, mutasi_rows, jual_rows, harga_rows=()):
    """Kembalikan (baris, peringatan).

    log_rows    : tab Log tanpa judul     -> [Waktu, Staff, Rak, Produk, Rincian, Qty, Satuan, ED, SKU]
    mutasi_rows : tab Mutasi tanpa judul  -> [Waktu, Staff, Jenis, Dari, Ke, Produk, Rincian, Qty, Satuan, SKU, Nota]
    jual_rows   : tab Penjualan tanpa judul ->
                  [Awal, Akhir, Produk, Varian, Satuan Dasar, Qty Dasar, Qty Olsera, Omzet, Sebab]
                  Baris yang kolom Sebab-nya terisi adalah penjualan yang GAGAL
                  dikonversi ke satuan dasar. Dilewat di sini -- angkanya belum bisa
                  dipercaya -- tapi sengaja tetap ada di tab itu supaya kelihatan.
    harga_rows  : tab Harga tanpa judul, untuk kolom HPP + nilai. Kosong = kolom
                  nilai ikut kosong, hitungan qty tetap jalan.

    Kunci penggabungan adalah NAMA PRODUK, bukan SKU: tab Penjualan cuma punya nama
    (hasil pemetaan dari export Olsera lewat tab Peta Satuan Olsera). SKU tetap
    ikut ditampilkan kalau produknya pernah muncul di Log atau Mutasi.
    """
    # Waktu SO display terakhir. Timestamp penuh, sama seperti hitung_saldo.py.
    waktu_so = ""
    tanggal_display = set()
    for r in log_rows:
        if _kolom(r, 2) != DISPLAY:
            continue
        if _kolom(r, 0) > waktu_so:
            waktu_so = _kolom(r, 0)
        if _kolom(r, 0):
            tanggal_display.add(_kolom(r, 0)[:10])
    # Display sebesar toko ini bisa habis dua hari; hari bersambung = satu SO.
    sesi = sesi_so.terakhir(tanggal_display)
    tgl_so = waktu_so[:10]
    tgl_mulai = min(sesi) if sesi else ""

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
        # Hanya hitungan dari SESI SO terakhir yang jadi titik awal.
        if _kolom(r, 0)[:10] in sesi:
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

    # Penjualan: satu baris satu HARI (sejak tab Penjualan diisi dari upload POS
    # per tanggal). Dulu isinya rentang tanggal dan rentang yang melintasi hari SO
    # terpaksa dibuang seluruhnya; sekarang tidak ada lagi kasus itu.
    #
    # Yang tersisa cuma keremangan sehari: SO display dihitung pada JAM tertentu,
    # sedangkan penjualan cuma punya tanggal. Penjualan di hari SO itu sendiri
    # sebagian sudah tercermin di hitungan fisik (yang laku sebelum dihitung) dan
    # sebagian belum. Tidak bisa dipisah tanpa jam, jadi TIDAK dihitung, tapi
    # dilaporkan per produk supaya keliatan -- bukan dibuang diam-diam.
    hari_so = tgl_so[:10] if tgl_so else ""
    sehari = set()
    for r in jual_rows:
        tgl, produk = _kolom(r, 0)[:10], _kolom(r, 2)
        if not produk or not tgl:
            continue
        if _kolom(r, KOL_SEBAB):
            continue          # ada Sebab = gagal dikonversi, jangan dihitung
        satuan.setdefault(produk, _kolom(r, 6))
        if hari_so:
            if tgl < tgl_mulai:
                continue                  # sebelum SO, sudah tercermin di hitungan fisik
            if tgl <= hari_so:
                sehari.add(produk)        # hari-hari SO itu sendiri: tidak bisa dipisah
                continue
        terjual[produk] += _angka(_kolom(r, 5))

    produk_lintas = sehari

    per_sku, per_nama, _ = harga_lookup.muat_harga(harga_rows)

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
            catatan.append("ada penjualan di hari SO itu sendiri, belum ikut dihitung")

        sisa = "" if not tgl_so else _rapi(awal_qty + m - k - j)
        sat = satuan.get(produk, "")
        hpp, _jual = harga_lookup.cari(per_sku, per_nama, sku.get(produk, ""), produk, sat)
        baris.append([
            produk, sku.get(produk, ""), sat,
            _rapi(awal_qty), tgl_so or "belum pernah SO",
            _rapi(m), _rapi(k), _rapi(j), sisa,
            "" if hpp is None else _rapi(hpp),
            harga_lookup.nilai(sisa, hpp), harga_lookup.nilai(j, hpp),
            "; ".join(catatan),
        ])

    peringatan = []
    if not tgl_so:
        peringatan.append(
            "Area Display belum pernah di-SO, jadi kolom Sisa dikosongkan. "
            "Hitung display dulu di aplikasi, baru angka sisa ada artinya.")
    if sehari:
        peringatan.append(
            f"{len(sehari)} produk laku pada hari SO ({hari_so}) itu sendiri dan TIDAK "
            "dihitung: penjualan cuma punya tanggal, SO punya jam, jadi tidak bisa "
            "dipisah mana yang laku sebelum dan sesudah dihitung. Sisanya kelihatan "
            "sedikit lebih banyak daripada kenyataan, cuma untuk hari itu.")
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
    # tab Penjualan: Tanggal, SKU, Produk, Satuan, Qty, Qty Dasar, Satuan Dasar,
    #                Omzet, Bayar, Pelanggan, Sebab
    jual = [
        ["2026-06-15", "GLK", "Gula", "Pack", "100", "100", "Pack", "", "Lunas", "", ""],   # sebelum SO -> abaikan
        ["2026-08-17", "GLK", "Gula", "Pack", "12", "12", "Pack", "", "Lunas", "", ""],     # sesudah SO -> dihitung
        ["2026-08-17", "KPS", "Kopi Saset", "Pcs", "8", "8", "Pcs", "", "Lunas", "", ""],   # laku tapi tak pernah di-SO
        # Baris gagal dicocokkan: HARUS dilewat, kalau ikut terhitung sisa display salah.
        ["2026-08-17", "", "Gula", "", "2", "", "", "50000", "Lunas", "",
         "SKU kosong di POS — barang diketik manual, belum ada di master"],
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
    assert "tidak ikut terhitung saat SO display" in kopi[12], f"catatan hilang: {kopi}"
    assert not peringatan, f"tidak ada penjualan di hari SO, harusnya sunyi: {peringatan}"

    # Penjualan pada HARI SO itu sendiri tidak boleh ikut, tapi WAJIB dilaporkan:
    # SO punya jam, penjualan cuma punya tanggal, jadi tidak bisa dipisah mana
    # yang laku sebelum dan sesudah barangnya dihitung.
    baris2, peringatan2 = hitung_display(
        log, mutasi,
        [["2026-08-10", "GLK", "Gula", "Pack", "50", "50", "Pack", "", "Lunas", "", ""]])
    g2 = {b[0]: b for b in baris2}["Gula"]
    assert g2[7] == 0, f"penjualan di hari SO tidak boleh dihitung: {g2}"
    assert "hari SO itu sendiri" in g2[12], f"catatan baris hilang: {g2}"
    assert peringatan2 and "hari SO" in peringatan2[0], peringatan2

    # Penjualan SESUDAH hari SO, walau tanggalnya berdempetan, tetap dihitung.
    baris2b, _ = hitung_display(
        log, mutasi,
        [["2026-08-11", "GLK", "Gula", "Pack", "50", "50", "Pack", "", "Lunas", "", ""]])
    assert {b[0]: b for b in baris2b}["Gula"][7] == 50, "sehari sesudah SO harus ikut"

    # Belum pernah SO display sama sekali -> kolom Sisa kosong, bukan angka minus besar.
    baris3, peringatan3 = hitung_display([], mutasi, jual)
    g3 = {b[0]: b for b in baris3}["Gula"]
    assert g3[8] == "", f"tanpa SO, Sisa harus kosong: {g3}"
    assert g3[4] == "belum pernah SO", g3
    assert g3[5] == 39, f"tanpa SO, semua isi ulang ikut: {g3}"    # 9 + 30
    assert peringatan3 and "belum pernah di-SO" in peringatan3[0], peringatan3

    # Tanpa tab Harga, tiga kolom nilai kosong tapi qty tetap benar.
    assert gula[9] == "" and gula[10] == "" and gula[11] == "", f"tanpa harga harus kosong: {gula}"

    harga = [["GLK", "Gula", "Pack", 1, 12000, 15000, "HJ3", "Bahan Kue"]]
    dgn = {b[0]: b for b in hitung_display(log, mutasi, jual, harga)[0]}
    g = dgn["Gula"]
    assert g[9] == 12000, f"HPP lewat SKU gagal: {g}"
    assert g[10] == 34 * 12000, f"Nilai Sisa salah: {g}"
    assert g[11] == 12 * 12000, f"Nilai Terjual salah: {g}"
    k = dgn["Kopi Saset"]
    assert k[9] == "" and k[10] == "", f"produk tanpa harga harus kosong: {k}"
    # Sisa minus tetap dinilai -- itu justru kerugian yang mau dilihat.
    dgn2 = {b[0]: b for b in hitung_display(log, mutasi, jual,
            harga + [["KPS", "Kopi Saset", "Pcs", 1, 2000, 3000, "HJ3", "X"]])[0]}
    assert dgn2["Kopi Saset"][10] == -16000, f"nilai sisa minus salah: {dgn2['Kopi Saset']}"

    # SO display dua hari bersambung = satu sesi; hari pertama tidak boleh hilang.
    log_dua = [
        ["2026-08-30 20:00:00", "ichan", "Area Display", "Gula", "", "20", "Pack", "", "GLK"],
        ["2026-08-31 19:00:00", "dewo", "Area Display", "Ceres", "", "5", "Pcs", "", "CRS"],
    ]
    bd, _ = hitung_display(log_dua, [], [])
    perd = {b[0]: b for b in bd}
    assert perd["Gula"][3] == 20, f"hari pertama sesi display hilang: {perd['Gula']}"
    assert perd["Ceres"][3] == 5, perd["Ceres"]
    assert perd["Gula"][4] == "2026-08-31", f"Tgl SO = hari selesai: {perd['Gula']}"

    print("semua uji hitung_display LOLOS")


# --- Tidak lagi menulis sheet -----------------------------------------------
#
# Berkas ini sekarang MODUL MURNI. Yang menulis tab Stok adalah `hitung_stok.py`,
# yang memanggil fungsi hitung di atas untuk Area Display lalu menggabungkannya dengan
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
