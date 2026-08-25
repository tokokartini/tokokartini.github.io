# -*- coding: utf-8 -*-
"""Pencari HPP dari tab 'Harga'. Dipakai hitung_saldo.py, saldo_display.py,
dan selisih_so.py.

Dipisah jadi modul sendiri supaya semuanya memakai aturan pencarian yang persis
sama — kalau salah satu menghitung nilai dengan cara berbeda, angka gudang dan
angka display tidak bisa dijumlahkan dan angka selisih ikut salah.

Dua jalan cari, berurutan:

1. **Lewat SKU** — paling tepat, satu SKU satu harga.
2. **Lewat (nama produk, satuan)** — untuk baris yang tidak punya SKU. Tab
   Penjualan cuma menyimpan nama produk, jadi baris Area Display di tab Stok bisa
   saja tanpa SKU sampai produknya pernah ikut SO atau mutasi.

Kalau satu (produk, satuan) ternyata punya DUA HPP berbeda, harganya dianggap
tidak bisa dipastikan dan baris itu dibiarkan kosong, bukan diambil salah satu.
Angka nilai yang salah diam-diam lebih berbahaya daripada kolom kosong.
"""

# Bentuk baris tab Harga: SKU, Produk, Satuan, Isi, HPP, Harga Jual, Slot, Kategori
KOL_SKU, KOL_PRODUK, KOL_SATUAN, KOL_HPP, KOL_JUAL = 0, 1, 2, 4, 5


def muat_harga(harga_rows):
    """Kembalikan (per_sku, per_nama, bentrok).

    per_sku  : {sku: (hpp, jual)}
    per_nama : {(produk, satuan): (hpp, jual)}  -- tanpa yang bentrok
    bentrok  : daftar (produk, satuan) yang punya lebih dari satu HPP
    """
    per_sku = {}
    kandidat = {}
    for r in harga_rows:
        sku = _teks(r, KOL_SKU)
        produk, satuan = _teks(r, KOL_PRODUK), _teks(r, KOL_SATUAN)
        hpp, jual = _angka(_teks(r, KOL_HPP)), _angka(_teks(r, KOL_JUAL))
        if hpp is None:
            continue
        if sku:
            per_sku[sku] = (hpp, jual)
        if produk and satuan:
            kandidat.setdefault((produk, satuan), []).append((hpp, jual))

    per_nama, bentrok = {}, []
    for kunci, daftar in kandidat.items():
        harga_beda = {h for h, _ in daftar}
        if len(harga_beda) > 1:
            bentrok.append(kunci)
            continue
        # HPP-nya sama, jadi nilai stok tidak ambigu. Tapi harga jual bisa cuma
        # terisi di salah satu slot (grosir sering kosong, HJ3 terisi) -- ambil
        # yang punya harga jual supaya tidak hilang percuma.
        per_nama[kunci] = next((d for d in daftar if d[1] is not None), daftar[0])
    return per_sku, per_nama, bentrok


def cari(per_sku, per_nama, sku, produk, satuan):
    """Kembalikan (hpp, jual); keduanya None kalau harganya tidak bisa dipastikan."""
    if sku and sku in per_sku:
        return per_sku[sku]
    return per_nama.get((produk, satuan), (None, None))


def nilai(qty, hpp):
    """qty x hpp, dibulatkan ke rupiah. Kembalikan "" kalau salah satunya tak ada."""
    if hpp is None or qty == "" or qty is None:
        return ""
    try:
        return round(float(qty) * float(hpp))
    except (TypeError, ValueError):
        return ""


def _teks(baris, i):
    return str(baris[i]).strip() if i < len(baris) and baris[i] is not None else ""


def _angka(s):
    if not s:
        return None
    s = str(s).replace("Rp", "").replace(" ", "")
    # Tab Harga ditulis skrip sebagai angka biasa, tapi kalau ada yang mengetik
    # ulang manual bisa saja masuk format Indonesia lagi.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def uji():
    harga = [
        ["KLP-G", "Klip", "Bal (20 Kg)", 1, 1411172, 1560000, "Grosir", "Packaging"],
        ["KLP-2", "Klip", "Pack (10 Bks)", 80, 17639.65, 22000, "HJ2", "Packaging"],
        # dua SKU, nama+satuan sama, HPP sama -> boleh dipakai lewat nama
        ["ALC-G", "Alu Cup", "Pack (10pcs)", 1, 8620, "", "Grosir", "Alu Cup"],
        ["ALC-3", "Alu Cup", "Pack (10pcs)", 1, 8620, 10000, "HJ3", "Alu Cup"],
        # nama+satuan sama tapi HPP BEDA -> tidak boleh ditebak
        ["DUA-A", "Ragu", "Pcs", 1, 100, 150, "HJ3", "X"],
        ["DUA-B", "Ragu", "Pcs", 1, 250, 300, "HJ2", "X"],
        # tanpa HPP -> tidak masuk peta sama sekali
        ["NOL", "Tanpa Harga", "Pcs", 1, "", "", "HJ3", "X"],
    ]
    per_sku, per_nama, bentrok = muat_harga(harga)

    assert per_sku["KLP-G"] == (1411172, 1560000)
    assert "NOL" not in per_sku, "baris tanpa HPP tidak boleh masuk"
    assert bentrok == [("Ragu", "Pcs")], f"bentrok tak terdeteksi: {bentrok}"
    assert ("Ragu", "Pcs") not in per_nama, "HPP bentrok tidak boleh dipakai"
    # HPP sama di dua slot; harga jual cuma ada di HJ3, dan itu yang harus menang.
    assert per_nama[("Alu Cup", "Pack (10pcs)")] == (8620, 10000), per_nama[("Alu Cup", "Pack (10pcs)")]

    # SKU menang atas nama
    assert cari(per_sku, per_nama, "KLP-2", "Klip", "Bal (20 Kg)")[0] == 17639.65
    # tanpa SKU -> lewat nama
    assert cari(per_sku, per_nama, "", "Alu Cup", "Pack (10pcs)")[0] == 8620
    # bentrok -> kosong, bukan tebakan
    assert cari(per_sku, per_nama, "", "Ragu", "Pcs") == (None, None)
    # tak dikenal -> kosong
    assert cari(per_sku, per_nama, "", "Entah", "Pcs") == (None, None)
    # SKU tak dikenal tapi nama cocok -> tetap ketemu lewat nama
    assert cari(per_sku, per_nama, "ASING", "Alu Cup", "Pack (10pcs)")[0] == 8620

    assert nilai(3, 8620) == 25860
    assert nilai(0, 8620) == 0
    assert nilai(-8, 100) == -800, "sisa minus tetap dihitung nilainya"
    assert nilai(5, None) == "" and nilai("", 100) == ""

    print("semua uji harga_lookup LOLOS")


if __name__ == "__main__":
    uji()
