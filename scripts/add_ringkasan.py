# -*- coding: utf-8 -*-
"""Pasang tab 'Ringkasan' — satu halaman keadaan hari ini.

    python3 -u add_ringkasan.py            # pasang / perbarui tab Ringkasan
    python3 -u add_ringkasan.py --uji      # pasang, uji pakai data palsu, lalu pulihkan

Semua tab lain isinya rincian. Tidak ada satu pun yang menjawab "hari ini saya
harus ngapain". Tab Ringkasan menjawab itu: berapa nilai stok, lokasi mana yang
belum di-SO, produk apa yang minus, barang apa yang mau ED, dan mana yang selisih.

Semua isinya FORMULA yang membaca tab lain, jadi ikut terbarui sendiri. Dua tab
sumbernya (Stok & Selisih SO) ditulis skrip, dan penanda basi di baris 1 masing-
masing ikut ditampilkan di sini supaya ketahuan kalau angkanya sudah lewat sehari.

`--uji` mengisi tab Stok dengan data palsu, membaca kembali Ringkasan untuk
memeriksa angkanya, lalu MEMULIHKAN tab itu dengan menjalankan ulang
`hitung_stok.py`. Aman karena tab Stok memang milik skrip dan ditimpa tiap kali
dijalankan. Log TIDAK pernah disentuh.

Locale sheet `in_ID`: pemisah argumen `;`.
"""
import argparse
import os
import socket
import subprocess
import sys
import time
import warnings
from pathlib import Path

TAB = "Ringkasan"

# Teks di kolom A, formula di kolom B. None = baris kosong, ("#", judul) = judul bagian.
BARIS = [
    ("#", "STOK OPNAME"),
    ("SO terakhir",
     '=IFERROR(INDEX(SORT(FILTER(Log!A2:A;Log!A2:A<>"");1;FALSE);1;1);"belum pernah SO")'),
    ("Baris hasil SO seluruhnya", '=COUNTA(Log!A2:A)'),
    ("Lokasi yang sudah pernah di-SO", '=IFERROR(COUNTA(UNIQUE(FILTER(Log!C2:C;Log!C2:C<>"")));0)'),
    ("Area Display sudah di-SO?",
     '=IF(COUNTIF(Log!C2:C;"Area Display")>0;"sudah";"BELUM — sisa display belum bisa dihitung")'),
    None,

    # Tab Stok: baris 1 penanda, 2 judul, data mulai baris 3. A Lokasi ... J Sisa,
    # K HPP, L Nilai Sisa.
    ("#", "NILAI STOK (HPP)"),
    ("Gudang", '=IFERROR(SUMIF(Stok!A3:A;"<>Area Display";Stok!L3:L);0)'),
    ("Area Display", '=IFERROR(SUMIF(Stok!A3:A;"Area Display";Stok!L3:L);0)'),
    ("Jumlah", '=B8+B9'),
    # Penanda di Stok!A1 sudah berbunyi sendiri kalau angkanya lewat sehari.
    ("Stok", '=IFERROR(Stok!A1;"tab Stok belum ada")'),
    ("Harga", '=IFERROR(Harga!J1;"tab Harga belum ada")'),
    None,

    ("#", "PERLU PERHATIAN"),
    ("Produk display sisa MINUS",
     '=IFERROR(COUNTIFS(Stok!A3:A;"Area Display";Stok!J3:J;"<0");0)'),
    ("Nilai display minus",
     '=IFERROR(SUMIFS(Stok!L3:L;Stok!A3:A;"Area Display";Stok!J3:J;"<0");0)'),
    ("Produk gudang sisa MINUS",
     '=IFERROR(COUNTIFS(Stok!A3:A;"<>Area Display";Stok!J3:J;"<0");0)'),
    ("Baris stok tanpa harga",
     '=IFERROR(COUNTBLANK(Stok!K3:K)-COUNTBLANK(Stok!A3:A);0)'),
    None,

    ("#", "KADALUARSA"),
    ("Sudah LEWAT ED", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"LEWAT");0)'),
    ("Nilai yang sudah lewat", '=IFERROR(SUMIF(Kadaluarsa!J2:J;"LEWAT";Kadaluarsa!K2:K);0)'),
    ("ED dalam 30 hari", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"30 hari");0)'),
    ("ED dalam 90 hari", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"90 hari");0)'),
    None,

    # SUMPRODUCT, BUKAN COUNTIFS. Kolom waktu di tab Mutasi itu TEKS, dan COUNTIFS
    # dengan syarat ">=tanggal" menganggapnya angka sehingga tidak pernah cocok --
    # hasilnya diam-diam 0, tanpa error. Perbandingan teks di SUMPRODUCT jalan, dan
    # bentuk YYYY-MM-DD urutan hurufnya sama dengan urutan tanggalnya.
    ("#", "MUTASI BARANG"),
    ("Baris mutasi seluruhnya", '=COUNTA(Mutasi!A2:A)'),
    ("7 hari terakhir",
     '=IFERROR(SUMPRODUCT((Mutasi!A2:A<>"")*'
     '(LEFT(Mutasi!A2:A;10)>=TEXT(TODAY()-7;"yyyy-mm-dd")));0)'),
    ("Isi ulang display 7 hari terakhir",
     '=IFERROR(SUMPRODUCT((Mutasi!E2:E="Area Display")*'
     '(LEFT(Mutasi!A2:A;10)>=TEXT(TODAY()-7;"yyyy-mm-dd")));0)'),
    None,

    # Alasan sama: kolom Tanggal di tab Barang Rusak juga teks. Cocokkan awalan
    # "2026-08*" pakai wildcard, itu perbandingan teks yang memang jalan.
    ("#", "KERUGIAN BARANG"),
    ("Barang rusak bulan ini",
     '=IFERROR(COUNTIF(\'Barang Rusak\'!A2:A;TEXT(TODAY();"yyyy-mm")&"*");0)'),
    ("Nilai kerugian bulan ini",
     '=IFERROR(SUMIF(\'Barang Rusak\'!A2:A;TEXT(TODAY();"yyyy-mm")&"*";'
     '\'Barang Rusak\'!I2:I);0)'),
    ("Nilai kerugian seluruhnya", '=IFERROR(SUM(\'Barang Rusak\'!I2:I);0)'),
    None,

    # Tab Selisih SO juga baris 1 penanda, 2 judul, data mulai 3.
    ("#", "SELISIH SO"),
    ("Produk yang selisih", '=IFERROR(COUNT(\'Selisih SO\'!H3:H);0)'),
    ("Nilai barang kurang", '=IFERROR(-SUMIF(\'Selisih SO\'!J3:J;"<0");0)'),
    ("Nilai barang lebih", '=IFERROR(SUMIF(\'Selisih SO\'!J3:J;">0");0)'),
    ("Selisih", '=IFERROR(\'Selisih SO\'!A1;"belum pernah dihitung")'),
    None,

    # Ditaruh PALING BAWAH, seperti KERUGIAN BARANG dulu: menyisipkan blok di
    # tengah menggeser nomor baris semua blok sesudahnya, dan format rupiah dari
    # susunan lama nyangkut di baris yang artinya sudah berubah (`Worksheet.clear()`
    # cuma menghapus ISI, bukan FORMAT -- pernah bikin "3 produk" tampil "Rp 3").
    #
    # Kolom tab Penjualan: A Tanggal, B SKU, C Produk, D Satuan, E Qty,
    #                      F Qty Dasar, G Satuan Dasar, H Omzet, I Bayar,
    #                      J Pelanggan, K Sebab
    ("#", "PENJUALAN & PIUTANG"),
    ("Penjualan terakhir tercatat",
     '=IFERROR(INDEX(SORT(FILTER(Penjualan!A2:A;Penjualan!A2:A<>"");1;FALSE);1);'
     '"belum ada penjualan diupload")'),
    ("Omzet bulan ini",
     '=IFERROR(SUMIF(Penjualan!A2:A;TEXT(TODAY();"yyyy-mm")&"*";Penjualan!H2:H);0)'),
    ("Piutang belum dibayar",
     '=IFERROR(SUMIF(Penjualan!I2:I;"Tempo";Penjualan!H2:H);0)'),
    # COUNTUNIQUEIFS, BUKAN COUNTUNIQUE(FILTER(...)). Yang kedua melaporkan **1**
    # waktu tab Penjualan masih kosong -- sel kosong hasil FILTER ikut terhitung
    # sebagai satu nilai unik, dan IFERROR tidak menangkapnya karena tidak ada
    # galat. Diuji langsung di sheet 2026-08-26: kosong -> 1 (salah) lawan 0 (benar),
    # terisi dua pelanggan -> dua-duanya 2. Syarat `"?*"` membuang nama kosong.
    ("Pelanggan yang nunggak",
     '=IFERROR(COUNTUNIQUEIFS(Penjualan!J2:J;Penjualan!I2:I;"Tempo";'
     'Penjualan!J2:J;"?*");0)'),
    # Baris ber-Sebab = penjualan yang TIDAK bisa dicocokkan ke master, jadi tidak
    # ikut mengurangi stok display. Ditampilkan supaya kelihatan, bukan dibuang:
    # kalau angkanya besar, sisa display kelihatan lebih banyak daripada kenyataan.
    ("Penjualan tak cocok ke master",
     '=IFERROR(COUNTIF(Penjualan!K2:K;"?*");0)'),
    ("Nilainya",
     '=IFERROR(SUMIF(Penjualan!K2:K;"?*";Penjualan!H2:H);0)'),
]

# Baris yang isinya rupiah, DIHITUNG dari daftar BARIS -- dulu nomornya ditulis
# tangan ("B8", "B9", ...) dan itu bom waktu: menambah satu baris di tengah
# menggeser semuanya, sedangkan `Worksheet.clear()` tidak menghapus FORMAT, jadi
# pola rupiah lama nyangkut di baris yang sekarang berisi hitungan biasa dan
# "3 produk" tampil sebagai "Rp 3". Sekarang label yang jadi patokan, bukan nomor.
LABEL_RUPIAH = {
    "Gudang", "Area Display", "Jumlah",
    "Nilai display minus",
    "Nilai yang sudah lewat",
    "Nilai kerugian bulan ini", "Nilai kerugian seluruhnya",
    "Nilai barang kurang", "Nilai barang lebih",
    "Omzet bulan ini", "Piutang belum dibayar", "Nilainya",
}
RUPIAH = [f"B{i + 1}" for i, b in enumerate(BARIS)
          if b and b[0] in LABEL_RUPIAH]

BLOK = [
    ("D1", "PROGRES SO PER LOKASI",
     '=IFERROR(QUERY(Log!A2:I;'
     '"select C, count(D), max(A) where C is not null and C <> \'\' '
     'group by C order by C '
     'label C \'Lokasi\', count(D) \'Produk\', max(A) \'Terakhir\'";0);'
     '"belum ada SO")'),
    ("I1", "NILAI STOK PER LOKASI",
     '=IFERROR(QUERY(Stok!A3:L;'
     '"select A, count(B), sum(L) where A is not null and A <> \'\' '
     'group by A order by A '
     'label A \'Lokasi\', count(B) \'Jumlah SKU\', sum(L) \'Nilai HPP\'";0);'
     '"belum ada stok — jalankan hitung saldo")'),
    ("S1", "PIUTANG PER PELANGGAN",
     '=IFERROR(QUERY(Penjualan!A2:K;'
     '"select J, sum(H), max(A) where I = \'Tempo\' and J is not null and J <> \'\' '
     'group by J order by sum(H) desc '
     'label J \'Pelanggan\', sum(H) \'Belum dibayar\', max(A) \'Terakhir\'";0);'
     '"tidak ada tempo")'),
    ("N1", "10 SELISIH TERBESAR",
     '=IFERROR(QUERY(\'Selisih SO\'!A3:K;'
     '"select D, B, H, J where H is not null order by J asc limit 10 '
     'label D \'Produk\', B \'Lokasi\', H \'Selisih\', J \'Nilai\'";0);'
     '"tidak ada selisih")'),
]


# --- Jaringan ---------------------------------------------------------------

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def buka(sh, judul, kolom, baris):
    import gspread
    try:
        ws = sh.worksheet(judul)
        if ws.col_count < kolom or ws.row_count < baris:
            ws.resize(rows=max(ws.row_count, baris), cols=max(ws.col_count, kolom))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(judul, rows=baris, cols=kolom)


def pasang(ws):
    ws.clear()
    kiri = []
    for b in BARIS:
        if b is None:
            kiri.append(["", ""])
        elif b[0] == "#":
            kiri.append([b[1], ""])
        else:
            kiri.append([b[0], b[1]])
    ws.update(values=kiri, range_name="A1", value_input_option="USER_ENTERED")

    for sel, judul, rumus in BLOK:
        kol = sel[0]
        ws.update(values=[[judul], [rumus]], range_name=f"{kol}1",
                  value_input_option="USER_ENTERED")

    # Judul bagian ditebalkan supaya kelihatan blok-bloknya.
    tebal = [f"A{i + 1}" for i, b in enumerate(BARIS) if b and b[0] == "#"]
    tebal += [s for s, _, _ in BLOK]
    for sel in tebal:
        ws.format(sel, {"textFormat": {"bold": True}})
    # Kolom B dinolkan formatnya dulu. `clear()` cuma menghapus ISI, bukan format --
    # jadi kalau susunan barisnya bergeser, format rupiah dari susunan lama nyangkut
    # di baris yang sekarang berisi hitungan, dan "3 produk" tampil sebagai "Rp 3".
    ws.format("B1:B60", {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}})
    for sel in RUPIAH:
        ws.format(sel, {"numberFormat": {"type": "NUMBER", "pattern": '"Rp" #,##0'}})
    ws.columns_auto_resize(0, 1)


def periksa(ws):
    """Kembalikan daftar sel yang isinya galat formula."""
    galat = []
    for i, baris in enumerate(ws.get_all_values(), start=1):
        for j, sel in enumerate(baris):
            t = str(sel).strip()
            if t.startswith("#") and t.rstrip("!?") in (
                    "#ERROR", "#REF", "#VALUE", "#NAME", "#N/A", "#DIV/0"):
                galat.append(f"{chr(64 + j + 1)}{i} = {t}")
    return galat


def uji_dengan_data_palsu(sh, ws):
    """Isi tab Stok dengan data palsu, periksa angka Ringkasan, lalu pulihkan."""
    stok = sh.worksheet("Stok")
    stok.clear()
    stok.update(values=[
        ["(uji)", ""],
        ["Lokasi", "SKU", "Produk", "Satuan", "Hasil SO", "Tgl SO", "Masuk", "Keluar",
         "Terjual", "Sisa", "HPP", "Nilai Sisa", "Catatan"],
        ["Gudang Ciherang", "A1", "Gula", "Pack", 10, "2026-08-20", 0, 0, "", 10, 12000, 120000, ""],
        ["Gudang Ciherang", "A2", "Ceres", "Pcs", 5, "2026-08-20", 0, 0, "", 5, 5000, 25000, ""],
        ["Gudang Packaging", "A3", "Mika", "Pcs", 3, "2026-08-21", 0, 0, "", -2, 1000, -2000, ""],
        # baris tanpa harga -> harus ikut terhitung di "Baris stok tanpa harga"
        ["Gudang Packaging", "A4", "Entah", "Pcs", 1, "2026-08-21", 0, 0, "", 1, "", "", ""],
        ["Area Display", "A1", "Gula", "Pack", 4, "2026-08-20", 0, 0, 1, 3, 12000, 36000, ""],
        ["Area Display", "A9", "Kopi", "Pcs", 0, "2026-08-20", 0, 0, 8, -8, 2000, -16000, ""],
        ["Area Display", "A8", "Teh", "Pcs", 0, "2026-08-20", 0, 0, 5, -5, 1000, -5000, ""],
    ], range_name="A1")

    time.sleep(4)
    nilai = {r[0]: (r[1] if len(r) > 1 else "") for r in ws.get_all_values() if r and r[0]}

    def angka(teks):
        t = str(teks).replace("Rp", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            return float(t)
        except ValueError:
            return None

    gagal = []
    cek = [
        ("Gudang", 143000),               # 120000 + 25000 - 2000
        ("Area Display", 15000),          # 36000 - 16000 - 5000
        ("Jumlah", 158000),
        ("Produk display sisa MINUS", 2),
        ("Nilai display minus", -21000),
        ("Produk gudang sisa MINUS", 1),
        ("Baris stok tanpa harga", 1),
    ]
    for label, harus in cek:
        dapat = angka(nilai.get(label, ""))
        print(f"   {label:34} = {nilai.get(label, '')}", flush=True)
        if dapat != harus:
            gagal.append(f"{label}: dapat {dapat}, harusnya {harus}")

    blok = ws.get("I1:K8")
    print(f"   blok NILAI STOK PER LOKASI {len(blok)} baris:", flush=True)
    for r in blok[:5]:
        print("     ", r, flush=True)
    if not any("Gudang Ciherang" in str(r) for r in blok):
        gagal.append("blok NILAI STOK PER LOKASI tidak memuat Gudang Ciherang")

    print("   memulihkan tab Stok dari data asli...", flush=True)
    r = subprocess.run([sys.executable, "-u", str(Path(__file__).parent / "hitung_stok.py")],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        gagal.append(f"pemulihan hitung_stok.py GAGAL: {r.stderr[-300:]}")
    else:
        print("     hitung_stok.py dijalankan ulang", flush=True)
    return gagal


def jalan(pakai_uji):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    ws = buka(sh, TAB, 20, 60)
    pasang(ws)
    time.sleep(3)
    print(f"Tab '{TAB}' terpasang.", flush=True)

    galat = periksa(ws)
    if galat:
        print("GALAT FORMULA:", flush=True)
        for g in galat:
            print("   ", g, flush=True)
        return 1
    print("Tidak ada galat formula.", flush=True)

    if pakai_uji:
        print("\nUji dengan data palsu di tab Stok (Log tidak disentuh):", flush=True)
        gagal = uji_dengan_data_palsu(sh, ws)
        if gagal:
            print("\nGAGAL:", flush=True)
            for g in gagal:
                print("   ", g, flush=True)
            return 1
        print("   semua angka Ringkasan LOLOS", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true",
                    help="pasang lalu uji pakai data palsu, kemudian pulihkan tab saldo")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
