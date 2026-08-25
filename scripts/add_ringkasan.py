# -*- coding: utf-8 -*-
"""Pasang tab 'Ringkasan' — satu halaman keadaan hari ini.

    python3 -u add_ringkasan.py            # pasang / perbarui tab Ringkasan
    python3 -u add_ringkasan.py --uji      # pasang, uji pakai data palsu, lalu pulihkan

Sheet ini punya 13 tab dan semuanya rincian. Tidak ada satu pun yang menjawab
"hari ini saya harus ngapain". Tab Ringkasan menjawab itu: berapa nilai stok,
lokasi mana yang belum di-SO, produk apa yang minus, barang apa yang mau ED.

Semua isinya FORMULA yang membaca tab lain, jadi ikut terbarui sendiri. Yang tidak
otomatis cuma dua tab sumbernya (Stok Gudang & Stok Display) karena keduanya
ditulis skrip — stempel waktu hitungnya sengaja ditampilkan di sini supaya
ketahuan kalau angkanya sudah basi.

`--uji` mengisi Stok Gudang & Stok Display dengan data palsu, membaca kembali
Ringkasan untuk memeriksa angkanya, lalu MEMULIHKAN kedua tab itu dengan
menjalankan ulang skrip aslinya. Aman karena dua tab itu memang milik skrip dan
ditimpa tiap kali dijalankan. Log TIDAK pernah disentuh.

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

    ("#", "NILAI STOK (HPP)"),
    ("Gudang", '=IFERROR(SUM(\'Stok Gudang\'!K2:K);0)'),
    ("Area Display", '=IFERROR(SUM(\'Stok Display\'!K2:K);0)'),
    ("Jumlah", '=B8+B9'),
    ("Gudang dihitung", '=IFERROR(\'Stok Gudang\'!M1;"belum pernah dihitung")'),
    ("Display dihitung", '=IFERROR(\'Stok Display\'!O1;"belum pernah dihitung")'),
    ("Harga ditarik", '=IFERROR(Harga!J1;"tab Harga belum ada")'),
    None,

    ("#", "PERLU PERHATIAN"),
    ("Produk display sisa MINUS", '=IFERROR(COUNTIF(\'Stok Display\'!I2:I;"<0");0)'),
    ("Nilai display minus", '=IFERROR(SUMIF(\'Stok Display\'!I2:I;"<0";\'Stok Display\'!K2:K);0)'),
    ("Produk gudang sisa MINUS", '=IFERROR(COUNTIF(\'Stok Gudang\'!I2:I;"<0");0)'),
    ("Baris saldo tanpa harga",
     '=IFERROR(COUNTBLANK(\'Stok Gudang\'!J2:J)-COUNTBLANK(\'Stok Gudang\'!A2:A);0)'),
    None,

    ("#", "KADALUARSA"),
    ("Sudah LEWAT ED", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"LEWAT");0)'),
    ("Nilai yang sudah lewat", '=IFERROR(SUMIF(Kadaluarsa!J2:J;"LEWAT";Kadaluarsa!K2:K);0)'),
    ("ED dalam 30 hari", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"30 hari");0)'),
    ("ED dalam 90 hari", '=IFERROR(COUNTIF(Kadaluarsa!J2:J;"90 hari");0)'),
    None,

    ("#", "MUTASI BARANG"),
    ("Baris mutasi seluruhnya", '=COUNTA(Mutasi!A2:A)'),
    ("7 hari terakhir",
     '=IFERROR(COUNTIFS(Mutasi!A2:A;">="&TEXT(TODAY()-7;"yyyy-mm-dd");Mutasi!A2:A;"<>");0)'),
    ("Isi ulang display 7 hari terakhir",
     '=IFERROR(COUNTIFS(Mutasi!E2:E;"Area Display";'
     'Mutasi!A2:A;">="&TEXT(TODAY()-7;"yyyy-mm-dd"));0)'),
]

# Blok tabel di sebelah kanan.
BLOK = [
    ("D1", "PER LOKASI",
     '=IFERROR(QUERY(\'Stok Gudang\'!A2:K;'
     '"select A, max(F), count(B), sum(K) where A is not null and A <> \'\' '
     'group by A order by A '
     'label A \'Lokasi\', max(F) \'Tgl SO\', count(B) \'Jumlah SKU\', sum(K) \'Nilai HPP\'";0);'
     '"belum ada saldo gudang — jalankan scripts/hitung_saldo.py")'),
    ("I1", "10 DISPLAY PALING MINUS",
     '=IFERROR(QUERY(\'Stok Display\'!A2:K;'
     '"select A, I, K where I < 0 order by K asc limit 10 '
     'label A \'Produk\', I \'Sisa\', K \'Nilai\'";0);"tidak ada yang minus")'),
    ("M1", "10 PALING DEKAT ED",
     '=IFERROR(QUERY(Kadaluarsa!A2:K;'
     '"select A, C, E, J where A is not null and A <> \'\' order by A limit 10 '
     'label A \'ED\', C \'Produk\', E \'Qty\', J \'Status\'";0);"belum ada data ED")'),
]

# Baris yang isinya rupiah, bukan hitungan. Nomornya mengikuti urutan BARIS di atas:
# B8 Gudang, B9 Display, B10 Jumlah, B17 nilai display minus, B23 nilai yang lewat ED.
RUPIAH = ["B8", "B9", "B10", "B17", "B23"]


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
    """Isi dua tab saldo dengan data palsu, periksa angka Ringkasan, lalu pulihkan."""
    gudang = sh.worksheet("Stok Gudang")
    display = sh.worksheet("Stok Display")

    gudang.clear()
    gudang.update(values=[
        ["Lokasi", "SKU", "Produk", "Satuan", "Hasil SO", "Tgl SO", "Masuk", "Keluar",
         "Sisa", "HPP", "Nilai Sisa"],
        ["Gudang Ciherang", "A1", "Gula", "Pack", 10, "2026-08-20", 0, 0, 10, 12000, 120000],
        ["Gudang Ciherang", "A2", "Ceres", "Pcs", 5, "2026-08-20", 0, 0, 5, 5000, 25000],
        ["Gudang Packaging", "A3", "Mika", "Pcs", 3, "2026-08-21", 0, 0, -2, 1000, -2000],
        # baris tanpa harga -> harus ikut terhitung di "Baris saldo tanpa harga"
        ["Gudang Packaging", "A4", "Entah", "Pcs", 1, "2026-08-21", 0, 0, 1, "", ""],
    ], range_name="A1")

    display.clear()
    display.update(values=[
        ["Produk", "SKU", "Satuan", "Hasil SO", "Tgl SO", "Isi Ulang", "Keluar", "Terjual",
         "Sisa", "HPP", "Nilai Sisa", "Nilai Terjual (HPP)", "Catatan"],
        ["Gula", "A1", "Pack", 4, "2026-08-20", 0, 0, 1, 3, 12000, 36000, 12000, ""],
        ["Kopi", "A9", "Pcs", 0, "2026-08-20", 0, 0, 8, -8, 2000, -16000, 16000, ""],
        ["Teh", "A8", "Pcs", 0, "2026-08-20", 0, 0, 5, -5, 1000, -5000, 5000, ""],
    ], range_name="A1")

    time.sleep(4)
    nilai = {r[0]: (r[1] if len(r) > 1 else "") for r in ws.get_all_values() if r and r[0]}
    for k, v in nilai.items():
        if k in ("Gudang", "Area Display", "Jumlah", "Produk display sisa MINUS",
                 "Nilai display minus", "Produk gudang sisa MINUS", "Baris saldo tanpa harga"):
            print(f"   {k:34} = {v}", flush=True)

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
        ("Baris saldo tanpa harga", 1),
    ]
    for label, harus in cek:
        dapat = angka(nilai.get(label, ""))
        if dapat != harus:
            gagal.append(f"{label}: dapat {dapat}, harusnya {harus}")

    blok = ws.get("D1:G8")
    print(f"   blok PER LOKASI {len(blok)} baris:", flush=True)
    for r in blok[:5]:
        print("     ", r, flush=True)
    if not any("Gudang Ciherang" in str(r) for r in blok):
        gagal.append("blok PER LOKASI tidak memuat Gudang Ciherang")

    print("   memulihkan Stok Gudang & Stok Display dari data asli...", flush=True)
    for skrip in ("hitung_saldo.py", "saldo_display.py"):
        r = subprocess.run([sys.executable, "-u", str(Path(__file__).parent / skrip)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            gagal.append(f"pemulihan {skrip} GAGAL: {r.stderr[-300:]}")
        else:
            print(f"     {skrip} dijalankan ulang", flush=True)
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
        print("\nUji dengan data palsu di dua tab saldo (Log tidak disentuh):", flush=True)
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
