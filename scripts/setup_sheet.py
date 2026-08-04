# -*- coding: utf-8 -*-
"""Setup tab Log/Rekap/Template Olsera di sheet 'SO Toko Kartini' yang sudah ada."""
import json
import time
import warnings
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

# Suppress gspread deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = str(Path.home() / "Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

# locale id_ID: pemisah argumen ';', pemisah kolom array '\'
# Tanggal efektif = Rekap!G1. Log!A menyimpan waktu INPUT, bukan waktu upload —
# upload lewat tengah malam (lazim di malam akhir bulan) bikin TODAY() sudah
# ganti hari sementara SO terakhir masih tanggal kemarin. Jadi kosong berarti
# tanggal terbaru yang ADA di Log, bukan hari ini.
LATEST_LOG_DATE = (
    'IFERROR(INDEX(SORT(UNIQUE(FILTER(ARRAYFORMULA(LEFT(Log!A2:A;10));'
    'Log!A2:A<>""));1;0);1;1);"")'
)
TGL = f'IF($G$1="";{LATEST_LOG_DATE};TEXT($G$1;"yyyy-mm-dd"))'
TGL_TPL = f'IF(Rekap!$G$1="";{LATEST_LOG_DATE};TEXT(Rekap!$G$1;"yyyy-mm-dd"))'

# Template import Olsera menuntut nama produk berawalan "STOK ". Awalan itu
# ditambahkan di TAB OUTPUT saja -- Log tetap menyimpan nama produk asli supaya
# riwayat mentah bisa dicocokkan dengan master dan dengan tabel count_entries.
# Dipakai sebagai kolom pengganti Log!D di dalam sumber QUERY, jadi nomor Col
# di semua formula di bawah tidak bergeser.
PRODUK_STOK = 'ARRAYFORMULA(IF(Log!D2:D="";"";"STOK "&Log!D2:D))'

# Nama rak diteruskan apa adanya ke tab output. Sampai 2026-08-04 rak bernama
# "Rak 1".."Rak 5" dan diubah ke format Olsera ("rack1") lewat REGEXREPLACE.
# Sejak rak dinamai per lokasi ("Gudang Packaging", "Area Display", dst.) peta
# itu tidak berlaku lagi -- nama di Olsera disamakan dengan nama di tabel racks.
# Baris Log lama tetap tertulis "Rak 1".."Rak 3" (riwayat sengaja tidak diubah).
RACK_OLSERA = 'Log!C2:C'

# Log kini 9 kolom: A Waktu, B Staff, C Rak, D Produk, E Rincian, F Qty,
# G Satuan, H ED, I SKU. Array literal di bawah SENGAJA menyusun ulang kolom
# jadi Satuan, SKU, Qty supaya nomor Col di dalam string QUERY tetap sama
# seperti sebelum kolom Rincian ada -- jadi tidak ada query yang perlu diedit.
# Kolom E (Rincian) tidak ikut: teks itu untuk dibaca manusia di Log saja.
LOG_TAIL = 'Log!G2:G\\Log!I2:I\\Log!F2:F'

LOG_SRC = '{Log!A2:B\\' + RACK_OLSERA + '\\' + PRODUK_STOK + '\\' + LOG_TAIL + '\\Log!H2:H}'

# Satu QUERY untuk keempat kolom, BUKAN empat formula terpisah. Versi lama
# memakai ARRAYFORMULA(SUMIFS(...)) dan itu salah: SUMIFS tidak ter-vektor di
# dalam ARRAYFORMULA, jadi setiap baris ikut hasil baris pertama (ketahuan
# 2026-07-30: dua SKU beda qty 75 dan 22 sama-sama ditulis 75). Pola QUERY ini
# sama dengan tab Arsip Harian, yang sejak awal memang benar.
# Col1=Waktu, Col4=Produk, Col5=Satuan, Col6=SKU, Col7=Qty
REKAP = (
    '=IFERROR(QUERY(' + LOG_SRC + ';'
    '"select Col6, Col4, Col5, sum(Col7) '
    'where Col6<>\'\' and Col1 starts with \'"&' + TGL + '&"\' '
    'group by Col6, Col4, Col5 order by Col6 '
    'label sum(Col7) \'\'";0);"")'
)
TEMPLATE = (
    '=IFERROR(QUERY(' + LOG_SRC + ';'
    '"select max(Col1), Col4, Col5, Col6, sum(Col7), Col3, max(Col8) '
    'where Col6<>\'\' and Col1 starts with \'"&' + TGL_TPL + '&"\' '
    'group by Col4, Col5, Col6, Col3 '
    'label max(Col1) \'\', sum(Col7) \'\', max(Col8) \'\'";0);"")'
)
# Arsip: semua hari, dikelompokkan per tanggal+SKU, terbaru di atas.
# Col1=LEFT(Log!A;10) tanggal, Col2=Produk, Col3=Satuan, Col4=SKU, Col5=Qty
ARSIP = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;10))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)
# Arsip bulanan: sama persis, tanggal dipotong sampai bulan (LEFT ...;7).
# Dipasang juga oleh scripts/add_arsip_bulanan.py -- pakai skrip itu kalau SO
# sedang berjalan, karena setup_sheet.py mengosongkan Rekap!G1.
ARSIP_BULANAN = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;7))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}")
            time.sleep(delay)


def get_or_add_worksheet(sh, title, rows=3000, cols=8):
    """Reuse existing worksheet atau tambah baru; perbesar grid kalau kurang dari yang diminta."""
    try:
        ws = retry(lambda: sh.worksheet(title))
        if ws.col_count < cols or ws.row_count < rows:
            new_rows, new_cols = max(ws.row_count, rows), max(ws.col_count, cols)
            retry(lambda: ws.resize(rows=new_rows, cols=new_cols))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return retry(lambda: sh.add_worksheet(title, rows=rows, cols=cols))


def main():
    creds = Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))

    # Locale in_ID menentukan pemisah rumus ';'. Zona waktu Asia/Jakarta tetap
    # diset untuk penanganan tanggal yang konsisten di sheet ini (TGL/TGL_TPL
    # sendiri sudah tidak pakai TODAY() lagi, lihat komentar di atas).
    retry(lambda: sh.batch_update({"requests": [{
        "updateSpreadsheetProperties": {
            "properties": {"locale": "in_ID", "timeZone": "Asia/Jakarta"},
            "fields": "locale,timeZone",
        }
    }]}))

    # Verify locale was set
    props = retry(lambda: sh.fetch_sheet_metadata())["properties"]
    assert props.get("locale") == "in_ID", f"locale bukan in_ID: {props.get('locale')}"
    print(f"Locale verified: {props.get('locale')}")
    assert props.get("timeZone") == "Asia/Jakarta", f"timeZone bukan Asia/Jakarta: {props.get('timeZone')}"
    print(f"TimeZone verified: {props.get('timeZone')}")

    # Setup Log tab (cari berdasarkan nama tab, bukan asumsi tab pertama)
    try:
        log = retry(lambda: sh.worksheet("Log"))
    except gspread.exceptions.WorksheetNotFound:
        log = sh.sheet1
    retry(lambda: log.update_title("Log"))
    retry(lambda: log.update(values=[["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"]], range_name="A1:I1"))

    # Setup Rekap tab (+ kotak tanggal di F1/G1)
    rekap = get_or_add_worksheet(sh, "Rekap", rows=3000, cols=8)
    retry(lambda: rekap.update(values=[["SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:D1"))
    retry(lambda: rekap.update(values=[["Tanggal (kosong = hari SO terakhir)"]], range_name="F1"))
    retry(lambda: rekap.batch_clear(["B2:D2"]))  # sisa formula per-kolom versi lama
    retry(lambda: rekap.update(values=[[REKAP]], range_name="A2", raw=False))

    # Setup Template Olsera tab (kolom A:G tetap bersih untuk di-copy ke Olsera)
    tpl = get_or_add_worksheet(sh, "Template Olsera", rows=3000, cols=8)
    retry(lambda: tpl.update(values=[["time", "product", "variant", "sku", "qty", "rack", "expired_date"]], range_name="A1:G1"))
    retry(lambda: tpl.update(values=[[TEMPLATE]], range_name="A2", raw=False))

    # Setup Arsip Harian tab (semua hari, tidak ikut berganti saat tanggal berganti)
    arsip = get_or_add_worksheet(sh, "Arsip Harian", rows=50000, cols=5)
    retry(lambda: arsip.update(values=[["Tanggal", "SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:E1"))
    retry(lambda: arsip.update(values=[[ARSIP]], range_name="A2", raw=False))

    # Setup Arsip Bulanan tab (rekap per bulan, semua bulan di satu tab)
    arsip_bln = get_or_add_worksheet(sh, "Arsip Bulanan", rows=50000, cols=5)
    retry(lambda: arsip_bln.update(values=[["Bulan", "SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:E1"))
    retry(lambda: arsip_bln.update(values=[[ARSIP_BULANAN]], range_name="A2", raw=False))

    # Uji formula. Menulis ke Log HANYA bila Log masih kosong — kalau sudah ada
    # data SO, uji dilakukan dengan membaca tanggal yang sudah ada di sana.
    isi_log = retry(lambda: log.get_all_values())
    if len(isi_log) <= 1:
        retry(lambda: log.update(
            values=[[time.strftime("%Y-%m-%d") + " 00:00:00", "tes", "Rak 1", "Produk Uji",
                     "1 Pcs", 5, "Pcs", "", "TES-1"]],
            range_name="A2:I2"))
        tanggal_uji = time.strftime("%Y-%m-%d")
        bersihkan_log = True
    else:
        tanggal_uji = max((r[0][:10] for r in isi_log[1:] if r and r[0]), default="")
        bersihkan_log = False
        print(f"Log berisi {len(isi_log) - 1} baris — uji pakai tanggal {tanggal_uji}, Log tidak disentuh")

    retry(lambda: rekap.update(values=[[tanggal_uji]], range_name="G1"))
    time.sleep(3)

    cek = retry(lambda: rekap.get_values("A2:D2"))
    print(f"Rekap A2:D2: {cek}")
    cek2 = retry(lambda: tpl.get_values("A2:G2"))
    print(f"Template A2:G2: {cek2}")
    cek3 = retry(lambda: arsip.get_values("A2:E2"))
    print(f"Arsip A2:E2: {cek3}")
    cek4 = retry(lambda: arsip_bln.get_values("A2:E2"))
    print(f"Arsip Bulanan A2:E2: {cek4}")
    assert cek4 and len(cek4[0]) == 5 and cek4[0][0] == tanggal_uji[:7], \
        f"formula Arsip Bulanan gagal: {cek4}"

    if bersihkan_log:
        # Log ditulis oleh skrip ini sendiri barusan, jadi nilainya diketahui persis —
        # cek nilai eksak, bukan cuma "ada isi".
        assert cek and cek[0][:3] == ["TES-1", "Produk Uji", "Pcs"] and cek[0][3] == "5", \
            f"formula Rekap gagal: {cek}"
        assert cek2 and len(cek2[0]) > 4 and cek2[0][3] == "TES-1" and cek2[0][4] == "5", \
            f"formula Template gagal: {cek2}"
        assert cek3 and len(cek3[0]) > 4 and cek3[0] == [tanggal_uji, "TES-1", "Produk Uji", "Pcs", "5"], \
            f"formula Arsip gagal: {cek3}"
    else:
        # Data asli sudah ada di Log — nilai persisnya tidak diketahui di sini,
        # jadi cukup pastikan formula menghasilkan sesuatu (bukan kosong/error).
        assert cek and cek[0][0] and cek[0][3], f"formula Rekap gagal: {cek}"
        assert cek2 and len(cek2[0]) > 3 and cek2[0][3], f"formula Template gagal: {cek2}"
        assert cek3 and len(cek3[0]) > 0 and cek3[0][0] == tanggal_uji, f"formula Arsip gagal: {cek3}"

    # kosongkan kotak tanggal -> Rekap & Template ikut tanggal SO terakhir di Log
    retry(lambda: rekap.batch_clear(["G1"]))
    if bersihkan_log:
        retry(lambda: log.batch_clear(["A2:I2"]))

    # Update config
    cfg_path = Path(__file__).parent / "config.local.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["sheet_id"] = sh.id
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print(f"sheet setup: https://docs.google.com/spreadsheets/d/{sh.id}")
    print("Rekap formula verified [OK]")
    print("Template formula verified [OK]")


if __name__ == "__main__":
    main()
