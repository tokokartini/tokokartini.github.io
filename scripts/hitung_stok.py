# -*- coding: utf-8 -*-
"""Tulis tab 'Stok' — sisa stok semua lokasi, gudang dan Area Display sekaligus.

    python3 -u hitung_stok.py            # baca sheet, tulis tab Stok
    python3 -u hitung_stok.py --uji      # jalankan uji kedua rumus, tanpa jaringan

Dulu ini dua tab dan dua skrip. Digabung karena pertanyaan yang paling sering
diajukan ke sheet ini adalah "barang X ada berapa, di mana" — dan menjawabnya
dengan dua tab berarti membuka keduanya lalu mencocokkan sendiri. Selain itu dua
skrip terpisah bisa setengah terbarui: gudang hari ini, display kemarin, dan
tidak ada yang sadar.

Rumusnya tetap DUA, dan sengaja tidak disatukan:

    gudang  = hasil SO + masuk - keluar                  (tidak butuh data POS)
    display = hasil SO + isi ulang - keluar - penjualan  (butuh tab Penjualan)

Bedanya nyata: POS cuma menjual dari display, jadi cuma display yang berkurang
karena laku. Menyatukan rumusnya berarti salah satu sisi dipaksa memakai aturan
yang bukan miliknya. Yang disatukan cuma tabelnya.

Fungsi hitungnya tetap tinggal di `hitung_saldo.py` (gudang) dan
`saldo_display.py` (display) — dua-duanya sudah punya uji sendiri. Berkas ini
cuma menggabungkan hasilnya jadi satu tabel dan menulisnya.

Baris 1 tab Stok adalah penanda kapan dihitung, dan penandanya BERUBAH SENDIRI
jadi peringatan begitu lewat sehari. Stempel yang cuma berupa teks di kolom jauh
di kanan tidak pernah dibaca siapa pun.
"""
import argparse
import os
import socket
import sys
import time
import warnings

import harga_lookup
import hitung_saldo
import saldo_display

TAB = "Stok"
JUDUL = ["Lokasi", "SKU", "Produk", "Satuan", "Hasil SO", "Tgl SO",
         "Masuk", "Keluar", "Terjual", "Sisa", "HPP", "Nilai Sisa", "Catatan"]

# A1 memperingatkan sendiri kalau angkanya sudah lewat sehari. B1 diisi waktu
# hitung sebagai NILAI tanggal sungguhan, bukan teks, supaya bisa dibandingkan.
PENANDA = ('=IF($B$1="";"belum pernah dihitung";'
           'IF(TODAY()-INT($B$1)>=1;'
           '"⚠ ANGKA LAMA — dihitung "&TEXT($B$1;"d mmm HH:mm")&", jalankan ulang hitung saldo";'
           '"✓ Terbaru — dihitung "&TEXT($B$1;"d mmm HH:mm")))')


def gabung(baris_gudang, baris_display):
    """Satukan dua bentuk baris jadi satu tabel 13 kolom.

    gudang  : [lokasi, sku, produk, satuan, hasilSO, tglSO, masuk, keluar, sisa, hpp, nilai]
    display : [produk, sku, satuan, hasilSO, tglSO, isiUlang, keluar, terjual, sisa,
               hpp, nilaiSisa, nilaiTerjual, catatan]
    """
    out = []
    for b in baris_gudang:
        out.append([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], "", b[8], b[9], b[10], ""])
    for b in baris_display:
        # Kolom Masuk untuk display artinya isi ulang; keduanya "barang datang ke
        # lokasi ini", jadi satu kolom sudah cukup dan tidak menyesatkan.
        out.append([saldo_display.DISPLAY, b[1], b[0], b[2], b[3], b[4], b[5], b[6],
                    b[7], b[8], b[9], b[10], b[12]])
    # Area Display paling bawah supaya gudang-gudang berkelompok di atas.
    out.sort(key=lambda r: (r[0] == saldo_display.DISPLAY, r[0], str(r[2])))
    return out


def uji():
    hitung_saldo.uji()
    saldo_display.uji()

    g = [["Gudang A", "GLK", "Gula", "Pack", 10, "2026-08-20", 5, 2, 13, 12000, 156000]]
    d = [["Gula", "GLK", "Pack", 4, "2026-08-20", 3, 0, 1, 6, 12000, 72000, 12000, "catatan"]]
    hasil = gabung(g, d)
    assert len(hasil) == 2
    assert [r[0] for r in hasil] == ["Gudang A", "Area Display"], \
        f"display harus di bawah gudang: {[r[0] for r in hasil]}"
    gud, dis = hasil
    assert gud[8] == "" and gud[12] == "", f"gudang tidak punya Terjual/Catatan: {gud}"
    assert gud[9] == 13 and gud[11] == 156000, gud
    assert dis[1] == "GLK" and dis[2] == "Gula", f"kolom SKU/Produk display tertukar: {dis}"
    assert dis[6] == 3, f"isi ulang harus masuk kolom Masuk: {dis}"
    assert dis[8] == 1 and dis[9] == 6, dis
    assert dis[12] == "catatan", dis
    print("semua uji hitung_stok LOLOS")


KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def tulis_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    log = sh.worksheet("Log").get_all_values()[1:]
    mutasi = sh.worksheet("Mutasi").get_all_values()[1:]

    def opsional(nama):
        try:
            return sh.worksheet(nama).get_all_values()[1:]
        except gspread.exceptions.WorksheetNotFound:
            print(f"Tab '{nama}' belum ada — dilewat.", flush=True)
            return []

    harga = opsional("Harga")
    jual = opsional("Penjualan")
    print(f"Log {len(log)} | Mutasi {len(mutasi)} | Penjualan {len(jual)} | Harga {len(harga)}",
          flush=True)

    lokasi = {hitung_saldo._kolom(r, 2) for r in log if hitung_saldo._kolom(r, 2)}
    lokasi |= {hitung_saldo._kolom(r, 3) for r in mutasi} | {hitung_saldo._kolom(r, 4) for r in mutasi}
    lokasi -= hitung_saldo.MAYA | {hitung_saldo.DISPLAY, ""}

    baris_g = hitung_saldo.hitung_saldo(log, mutasi, lokasi, harga)
    baris_d, peringatan = saldo_display.hitung_display(log, mutasi, jual, harga)
    baris = gabung(baris_g, baris_d)
    print(f"{len(baris)} baris di {len(lokasi)} gudang + Area Display", flush=True)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < len(JUDUL) + 2:
            ws.resize(rows=max(ws.row_count, 20000), cols=len(JUDUL) + 2)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=20000, cols=len(JUDUL) + 2)

    sekarang = time.strftime("%Y-%m-%d %H:%M:%S")
    # Baris 1 penanda, baris 2 judul, data mulai baris 3.
    ws.update(values=[[PENANDA, sekarang]], range_name="A1", value_input_option="USER_ENTERED")
    ws.update(values=[JUDUL] + (baris or [["(belum ada data)"] + [""] * (len(JUDUL) - 1)]),
              range_name="A2")
    ws.format("A2:M2", {"textFormat": {"bold": True}})
    ws.format("A1", {"textFormat": {"bold": True}})
    ws.freeze(rows=2)

    total = sum(b[11] for b in baris if b[11] != "")
    tanpa = sum(1 for b in baris if b[10] == "")
    ws.update(values=[[f"Nilai stok Rp {total:,.0f}".replace(",", ".")],
                      [f"{tanpa} baris tanpa harga"]] + [[p] for p in peringatan],
              range_name="O1")
    print(f"Tab '{TAB}' ditulis ulang. Nilai stok Rp {total:,.0f}, {tanpa} tanpa harga",
          flush=True)
    for p in peringatan:
        print("  PERHATIAN:", p, flush=True)
    for b in baris[:5]:
        print("   ", b, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="jalankan uji, tanpa jaringan")
    a = ap.parse_args()
    if a.uji:
        uji()
        return 0
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    uji()
    return tulis_sheet()


if __name__ == "__main__":
    sys.exit(main())
