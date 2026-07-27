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

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"

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
            print(f"retry {i + 1}: {type(e).__name__}")
            time.sleep(delay)


def get_or_add_worksheet(sh, title, rows=3000, cols=8):
    """Reuse existing worksheet atau tambah baru."""
    try:
        return retry(lambda: sh.worksheet(title))
    except gspread.exceptions.WorksheetNotFound:
        return retry(lambda: sh.add_worksheet(title, rows=rows, cols=cols))


def main():
    creds = Credentials.from_service_account_file(
        KEY_PATH,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))

    # Note: locale set manually by user during sheet creation (API batch_update locale is unsupported)

    # Setup Log tab
    log = sh.sheet1
    retry(lambda: log.update_title("Log"))
    retry(lambda: log.update(values=[["Waktu", "Staff", "Rak", "Produk", "Satuan", "SKU", "Qty", "ED"]], range_name="A1:H1"))

    # Setup Rekap tab
    rekap = get_or_add_worksheet(sh, "Rekap", rows=3000, cols=6)
    retry(lambda: rekap.update(values=[["SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:D1"))
    retry(lambda: rekap.update(values=[REKAP], range_name="A2:D2", raw=False))

    # Setup Template Olsera tab
    tpl = get_or_add_worksheet(sh, "Template Olsera", rows=3000, cols=8)
    retry(lambda: tpl.update(values=[["time", "product", "variant", "sku", "qty", "rack", "expired_date"]], range_name="A1:G1"))
    retry(lambda: tpl.update(values=[[TEMPLATE]], range_name="A2", raw=False))

    # uji formula: baris contoh -> cek Rekap & Template ikut terisi
    retry(lambda: log.update(values=[["2026-01-01 00:00:00", "tes", "Rak 1", "Produk Uji", "Pcs", "TES-1", 5, ""]], range_name="A2:H2"))
    time.sleep(2)
    cek = retry(lambda: rekap.get_values("A2:D2"))
    print(f"Rekap A2:D2: {cek}")
    assert cek and cek[0][0] == "TES-1" and cek[0][3] == "5", f"formula Rekap gagal: {cek}"
    cek2 = retry(lambda: tpl.get_values("A2:G2"))
    print(f"Template A2:G2: {cek2}")
    assert cek2 and cek2[0][3] == "TES-1", f"formula Template gagal: {cek2}"
    retry(lambda: log.batch_clear(["A2:H2"]))

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
