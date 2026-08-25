# -*- coding: utf-8 -*-
"""Simpan potret saldo harian ke tab 'Arsip Saldo'.

Dipakai `hitung_saldo.py` (gudang) dan `saldo_display.py` (Area Display).

Kenapa perlu: tab Stok Gudang dan Stok Display DITIMPA tiap skripnya jalan, jadi
angka kemarin hilang. SO punya Arsip Harian dan Arsip Bulanan, saldo tidak punya
apa-apa — tidak bisa melihat tren, tidak bisa membuktikan stok tanggal sekian
berapa waktu ada selisih.

Aturan menulisnya sama dengan `import_penjualan.py`: yang ditimpa **hanya baris
milik tanggal dan lokasi yang sedang ditulis**. Jadi menjalankan `hitung_saldo.py`
dua kali sehari tidak menggandakan baris gudang, dan tidak ikut menghapus baris
Area Display yang ditulis skrip sebelahnya.
"""

TAB = "Arsip Saldo"
JUDUL = ["Tanggal", "Lokasi", "SKU", "Produk", "Satuan", "Sisa", "HPP", "Nilai"]


def gabung(lama, tanggal, lokasi_ditulis, baris_baru):
    """Kembalikan isi tab yang baru (tanpa judul).

    lama           : baris tab Arsip Saldo yang sekarang, tanpa judul
    tanggal        : `YYYY-MM-DD` potret ini
    lokasi_ditulis : himpunan lokasi yang jadi tanggung jawab pemanggil
    baris_baru     : [[lokasi, sku, produk, satuan, sisa, hpp, nilai], ...]

    Baris lama dipertahankan kecuali yang tanggal DAN lokasinya sama dengan yang
    sedang ditulis — itu potret usang yang memang harus diganti.
    """
    sisa = [r for r in lama
            if r and str(r[0]).strip()
            and not (str(r[0]).strip() == tanggal
                     and str(r[1]).strip() in lokasi_ditulis)]
    baru = [[tanggal] + list(b) for b in baris_baru]
    semua = sisa + baru
    # Terbaru di atas, lalu per lokasi, lalu per nama produk.
    semua.sort(key=lambda r: (str(r[0]), str(r[1]), str(r[3])))
    semua.reverse()
    semua.sort(key=lambda r: str(r[0]), reverse=True)
    return semua


def simpan(sh, tanggal, lokasi_ditulis, baris_baru):
    """Tulis potret ke tab Arsip Saldo. Kembalikan (jumlah baru, jumlah lama dipertahankan)."""
    import gspread
    try:
        ws = sh.worksheet(TAB)
        if ws.col_count < len(JUDUL):
            ws.resize(rows=max(ws.row_count, 50000), cols=len(JUDUL))
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=50000, cols=len(JUDUL))

    lama = ws.get_all_values()[1:]
    semua = gabung(lama, tanggal, lokasi_ditulis, baris_baru)
    ws.clear()
    ws.update(values=[JUDUL] + semua, range_name="A1")
    ws.format("A1:H1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
    return len(baris_baru), len(semua) - len(baris_baru)


def uji():
    lama = [
        ["2026-08-24", "Gudang Ciherang", "A1", "Gula", "Pack", 10, 12000, 120000],
        ["2026-08-25", "Gudang Ciherang", "A1", "Gula", "Pack", 8, 12000, 96000],
        ["2026-08-25", "Area Display", "A1", "Gula", "Pack", 3, 12000, 36000],
    ]
    baru = [["Gudang Ciherang", "A1", "Gula", "Pack", 5, 12000, 60000],
            ["Gudang Packaging", "A2", "Mika", "Pcs", 2, 1000, 2000]]

    hasil = gabung(lama, "2026-08-25", {"Gudang Ciherang", "Gudang Packaging"}, baru)

    # Potret gudang hari ini diganti, BUKAN ditambah.
    hari_ini_gudang = [r for r in hasil if r[0] == "2026-08-25" and r[1] == "Gudang Ciherang"]
    assert len(hari_ini_gudang) == 1, f"potret lama tidak terganti: {hari_ini_gudang}"
    assert hari_ini_gudang[0][5] == 5, hari_ini_gudang

    # Area Display hari ini milik skrip lain -> tidak boleh ikut terhapus.
    assert any(r[0] == "2026-08-25" and r[1] == "Area Display" for r in hasil), \
        "baris skrip sebelah ikut terhapus"
    # Tanggal lain utuh.
    assert any(r[0] == "2026-08-24" for r in hasil), "riwayat kemarin hilang"
    assert len(hasil) == 4, f"jumlah baris salah: {len(hasil)} -> {hasil}"
    # Terbaru di atas.
    assert hasil[0][0] == "2026-08-25" and hasil[-1][0] == "2026-08-24", hasil

    # Dijalankan lagi dengan hasil yang sama tidak menambah apa pun.
    lagi = gabung(hasil, "2026-08-25", {"Gudang Ciherang", "Gudang Packaging"}, baru)
    assert len(lagi) == 4, f"dijalankan ulang menggandakan baris: {len(lagi)}"

    print("semua uji arsip_saldo LOLOS")


if __name__ == "__main__":
    uji()
