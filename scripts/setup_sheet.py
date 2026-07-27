# -*- coding: utf-8 -*-
"""Buat spreadsheet 'SO Toko Kartini' + tab Log/Rekap/Template Olsera. Jalankan SEKALI."""
import json
import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHARE_TO = ["simaung.coorporate@gmail.com"]  # + email baru: python setup_sheet.py email@baru.com

# locale id_ID: pemisah argumen ';', pemisah kolom array '\'
REKAP = [
    '=IFERROR(SORT(UNIQUE(FILTER(Log!F2:F;Log!F2:F<>"")));"")',
    '=ARRAYFORMULA(IF(A2:A="";"";IFERROR(VLOOKUP(A2:A;{Log!F2:F\\Log!D2:D};2;FALSE);"")))',
    '=ARRAYFORMULA(IF(A2:A="";"";IFERROR(VLOOKUP(A2:A;{Log!F2:F\\Log!E2:E};2;FALSE);"")))',
    '=ARRAYFORMULA(IF(A2:A="";"";SUMIF(Log!F:F;A2:A;Log!G:G)))',
]
TEMPLATE = (
    '=IFERROR(FILTER({Log!A2:A\\Log!D2:D\\Log!E2:E\\Log!F2:F\\Log!G2:G\\Log!C2:C\\Log!H2:H};'
    'Log!F2:F<>"");"")'
)


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(delay)


def main():
    creds = Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.create("SO Toko Kartini"))
    retry(lambda: sh.batch_update({"requests": [{
        "updateSpreadsheetProperties": {"properties": {"locale": "id_ID"}, "fields": "locale"}
    }]}))

    log = sh.sheet1
    retry(lambda: log.update_title("Log"))
    retry(lambda: log.update("A1:H1", [["Waktu", "Staff", "Rak", "Produk", "Satuan", "SKU", "Qty", "ED"]]))

    rekap = retry(lambda: sh.add_worksheet("Rekap", rows=3000, cols=6))
    retry(lambda: rekap.update("A1:D1", [["SKU", "Produk", "Satuan", "Total Qty"]]))
    retry(lambda: rekap.update("A2:D2", [REKAP], raw=False))

    tpl = retry(lambda: sh.add_worksheet("Template Olsera", rows=3000, cols=8))
    retry(lambda: tpl.update("A1:G1", [["time", "product", "variant", "sku", "qty", "rack", "expired_date"]]))
    retry(lambda: tpl.update("A2", [[TEMPLATE]], raw=False))

    # uji formula: baris contoh -> cek Rekap & Template ikut terisi
    retry(lambda: log.update("A2:H2", [["2026-01-01 00:00:00", "tes", "Rak 1", "Produk Uji", "Pcs", "TES-1", 5, ""]]))
    time.sleep(2)
    cek = retry(lambda: rekap.get_values("A2:D2"))
    assert cek and cek[0][0] == "TES-1" and cek[0][3] == "5", f"formula Rekap gagal: {cek}"
    cek2 = retry(lambda: tpl.get_values("A2:G2"))
    assert cek2 and cek2[0][3] == "TES-1", f"formula Template gagal: {cek2}"
    retry(lambda: log.batch_clear(["A2:H2"]))

    for email in SHARE_TO + sys.argv[1:]:
        retry(lambda: sh.share(email, perm_type="user", role="writer"))

    cfg_path = Path(__file__).parent / "config.local.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["sheet_id"] = sh.id
    cfg_path.write_text(json.dumps(cfg, indent=2))
    print(f"sheet dibuat: https://docs.google.com/spreadsheets/d/{sh.id}")


if __name__ == "__main__":
    main()
