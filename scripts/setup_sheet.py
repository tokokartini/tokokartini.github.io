# -*- coding: utf-8 -*-
"""Setup tab Log + Arsip Harian di sheet 'SO Toko Kartini' yang sudah ada.

    python3 -u setup_sheet.py

Ini skrip pembangun ulang: dipakai kalau sheetnya harus dibuat dari awal, bukan
untuk pemakaian sehari-hari. Menyetel locale + zona waktu, menulis baris judul
Log, dan memasang formula tab Arsip Harian.

Dulu skrip ini juga membuat tab Rekap, Template Olsera, dan Arsip Bulanan.
Ketiganya dibuang 2026-08-25:

- **Template Olsera** untuk mengimpor hasil SO balik ke POS. Sopian tidak pernah
  memakainya -- yang dia butuh cuma hasil akhir dalam satuan terkecil, dan itu
  persis isi Arsip Harian.
- **Rekap** = Arsip Harian yang disaring satu tanggal lewat kotak `G1`. Data yang
  sama, cuma sudah difilter.
- **Arsip Bulanan** = Arsip Harian dikelompokkan per bulan. SO dilakukan sebulan
  sekali, jadi barisnya sama persis dengan Arsip Harian -- benar-benar duplikat.

Ikutan penting: awalan **`STOK `** di depan nama produk juga ikut dibuang. Awalan
itu tuntutan template impor Olsera, tapi tab Arsip Harian ikut memakainya. Tanpa
template, awalan itu cuma bikin nama produk di Arsip Harian tidak cocok dengan tab
Stok, Mutasi, dan Cari Barang.
"""
import json
import os
import time
import warnings
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = os.environ.get(
    "SO_KEY_PATH", str(Path.home() / "Documents/Claude AI/claude-code-powershel-1427d99324cd.json"))
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

LOG_HEADER = ["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"]

# Log 9 kolom: A Waktu, B Staff, C Rak, D Produk, E Rincian, F Qty, G Satuan,
# H ED, I SKU. Array literal di bawah menyusun ulang jadi Satuan, SKU, Qty --
# urutan itu dipertahankan supaya nomor Col di string QUERY tidak bergeser.
# Kolom E (Rincian) sengaja tidak ikut: teks itu untuk dibaca manusia di Log saja.
LOG_TAIL = 'Log!G2:G\\Log!I2:I\\Log!F2:F'

# Arsip Harian: semua hari, dikelompokkan per tanggal + SKU, terbaru di atas.
# Col1=tanggal, Col2=Produk, Col3=Satuan, Col4=SKU, Col5=Qty
#
# Agregatnya QUERY group by, BUKAN ARRAYFORMULA(SUMIFS(...)): SUMIFS tidak
# ter-vektor di dalam ARRAYFORMULA, tiap baris ikut hasil baris pertama. Pernah
# bikin dua SKU beda qty 75 dan 22 sama-sama ditulis 75 (ketahuan 2026-07-30).
ARSIP = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;10))\\Log!D2:D\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - jaringan toko sering menggantung
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", flush=True)
            time.sleep(delay)


def get_or_add_worksheet(sh, title, rows=3000, cols=8):
    """Pakai tab yang ada, atau tambah baru; perbesar grid kalau kurang."""
    try:
        ws = retry(lambda: sh.worksheet(title))
        if ws.row_count < rows or ws.col_count < cols:
            retry(lambda: ws.resize(rows=max(ws.row_count, rows), cols=max(ws.col_count, cols)))
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return retry(lambda: sh.add_worksheet(title, rows=rows, cols=cols))


def main():
    creds = Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"],
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))

    # Locale in_ID menentukan pemisah rumus ';' dan pemisah kolom array '\'.
    retry(lambda: sh.batch_update({"requests": [{
        "updateSpreadsheetProperties": {
            "properties": {"locale": "in_ID", "timeZone": "Asia/Jakarta"},
            "fields": "locale,timeZone",
        }
    }]}))
    props = retry(lambda: sh.fetch_sheet_metadata())["properties"]
    assert props.get("locale") == "in_ID", f"locale bukan in_ID: {props.get('locale')}"
    assert props.get("timeZone") == "Asia/Jakarta", f"timeZone salah: {props.get('timeZone')}"
    print(f"Locale {props['locale']}, zona {props['timeZone']} [OK]", flush=True)

    try:
        log = retry(lambda: sh.worksheet("Log"))
    except gspread.exceptions.WorksheetNotFound:
        log = sh.sheet1
        retry(lambda: log.update_title("Log"))
    retry(lambda: log.update(values=[LOG_HEADER], range_name="A1:I1"))

    arsip = get_or_add_worksheet(sh, "Arsip Harian", rows=50000, cols=5)
    retry(lambda: arsip.update(values=[["Tanggal", "SKU", "Produk", "Satuan", "Total Qty"]],
                               range_name="A1:E1"))
    retry(lambda: arsip.update(values=[[ARSIP]], range_name="A2", raw=False))

    # Uji formula. Menulis ke Log HANYA kalau Log masih kosong -- menulis ke Log
    # yang sudah berisi pernah menghilangkan data permanen (7 entri, 2026-07-30).
    isi_log = retry(lambda: log.get_all_values())
    if len(isi_log) <= 1:
        tanggal_uji = time.strftime("%Y-%m-%d")
        retry(lambda: log.update(
            values=[[tanggal_uji + " 00:00:00", "tes", "Rak 1", "Produk Uji",
                     "1 Pcs", 5, "Pcs", "", "TES-1"]], range_name="A2:I2"))
        time.sleep(3)
        cek = retry(lambda: arsip.get_values("A2:E2"))
        print(f"Arsip A2:E2: {cek}", flush=True)
        assert cek and cek[0] == [tanggal_uji, "TES-1", "Produk Uji", "Pcs", "5"], \
            f"formula Arsip gagal: {cek}"
        retry(lambda: log.batch_clear(["A2:I2"]))
    else:
        tanggal_uji = max((r[0][:10] for r in isi_log[1:] if r and r[0]), default="")
        time.sleep(3)
        cek = retry(lambda: arsip.get_values("A2:E2"))
        print(f"Log berisi {len(isi_log) - 1} baris — Log tidak disentuh. Arsip A2:E2: {cek}",
              flush=True)
        assert cek and cek[0] and cek[0][0] == tanggal_uji, f"formula Arsip gagal: {cek}"

    cfg_path = Path(__file__).parent / "config.local.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["sheet_id"] = sh.id
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print("Arsip Harian formula verified [OK]", flush=True)
    print(f"https://docs.google.com/spreadsheets/d/{sh.id}", flush=True)


if __name__ == "__main__":
    main()
