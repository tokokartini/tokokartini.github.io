# -*- coding: utf-8 -*-
"""Konversi baris tab 'Log' lama (satu baris per satuan) -> satu baris satuan dasar.

Baris lama:
  2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Krtn (50 Pack)  KTN-0008-G   1
  2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Pack            KTN-0008-3  25
Jadi:
  2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Pack            KTN-0008-3  75

Pakai:
  python convert_log_base_unit.py            # dry-run, cuma laporan
  python convert_log_base_unit.py --tulis    # backup tab Log lalu tulis ulang

Butuh: scripts/config.local.json {"supabase_url": ..., "service_role_key": ...}

Rekap/Template Olsera/Arsip Harian tidak disentuh -- ketiganya agregat per SKU di
atas Log, jadi ikut berubah sendiri. Rekap!G1 juga tidak disentuh.
"""
import json
import sys
import time
import warnings
from datetime import date
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"
TAB = "Log"
COLS = 8  # Waktu, Staff, rack, Produk, Satuan, SKU, Qty, ED


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(delay)


def fetch_products():
    """{sku: {mult, product_name, variant}} untuk SEMUA produk, aktif maupun tidak.

    Produk nonaktif tetap dipakai: baris Log lama bisa memuat SKU yang sudah
    dinonaktifkan sync, dan qty-nya tetap harus ikut dikonversi.
    """
    import requests

    cfg = json.loads((Path(__file__).parent / "config.local.json").read_text())
    url, key = cfg["supabase_url"].rstrip("/"), cfg["service_role_key"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    out, offset = {}, 0
    while True:
        r = requests.get(
            f"{url}/rest/v1/products?select=sku,product_name,variant,mult&limit=1000&offset={offset}",
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        chunk = r.json()
        for p in chunk:
            out[p["sku"]] = p
        if len(chunk) < 1000:
            return out
        offset += 1000


def base_unit_for(product_name, products):
    """Satuan dasar produk: mult == 1, kalau tak ada ambil mult terkecil."""
    units = [p for p in products.values() if p["product_name"] == product_name]
    if not units:
        return None
    exact = [u for u in units if float(u["mult"]) == 1]
    return exact[0] if exact else min(units, key=lambda u: float(u["mult"]))


def to_num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        pass
    # Cadangan kalau sheet mengembalikan angka terformat locale in_ID
    # ('1.775' = seribu tujuh ratus tujuh puluh lima, '2,5' = dua setengah).
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def convert(values, products):
    """values = get_all_values() termasuk header. Balikkan (baris_baru, laporan)."""
    header = values[0]
    groups = {}   # key -> dict akumulasi
    order = []    # urutan kemunculan pertama
    unknown = []  # baris yang produknya tak ada di products: dilewatkan apa adanya

    for raw in values[1:]:
        row = list(raw) + [""] * (COLS - len(raw))
        waktu, staff, rack, produk, satuan, sku, qty, ed = row[:COLS]
        if not str(produk).strip():
            continue

        prod = products.get(str(sku).strip())
        if not prod:
            unknown.append((row, "SKU tidak ada di products"))
            continue
        base = base_unit_for(prod["product_name"], products)
        if not base:
            unknown.append((row, "produk tanpa satuan di products"))
            continue

        key = (str(waktu)[:10], str(staff), str(rack), str(produk))
        if key not in groups:
            groups[key] = {
                "waktu": str(waktu),
                "staff": str(staff),
                "rack": str(rack),
                "produk": str(produk),
                "satuan": base["variant"],
                "sku": base["sku"],
                "qty": 0.0,
                "ed": str(ed).strip(),
                "asal": 0,
            }
            order.append(key)
        g = groups[key]
        g["qty"] += to_num(qty) * float(prod["mult"])
        g["asal"] += 1
        # Waktu paling awal di grup dipakai -- baris satu entri punya waktu sama,
        # tapi kalau beda (mis. entri diedit lalu di-upload lagi) yang pertama
        # yang mewakili kapan produk itu dihitung.
        if str(waktu) < g["waktu"]:
            g["waktu"] = str(waktu)
        if not g["ed"] and str(ed).strip():
            g["ed"] = str(ed).strip()

    rows = []
    for key in order:
        g = groups[key]
        qty = int(g["qty"]) if float(g["qty"]).is_integer() else round(g["qty"], 4)
        rows.append([g["waktu"], g["staff"], g["rack"], g["produk"], g["satuan"], g["sku"], qty, g["ed"]])

    # Baris yang tak bisa dikonversi ditempel apa adanya di akhir supaya qty-nya
    # tidak hilang dari Rekap; urutan Log tidak dipakai formula mana pun.
    for row, _ in unknown:
        rows.append(row[:COLS])

    laporan = {
        "baris_lama": len(values) - 1,
        "baris_baru": len(rows),
        "grup": len(order),
        "tak_dikenal": unknown,
    }
    return header[:COLS], rows, laporan


def main():
    tulis = "--tulis" in sys.argv

    products = fetch_products()
    print(f"products: {len(products)} SKU")

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))
    ws = retry(lambda: sh.worksheet(TAB))

    values = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))
    header, rows, lap = convert(values, products)

    print(f"Log: {lap['baris_lama']} baris -> {lap['baris_baru']} baris ({lap['grup']} entri)")
    if lap["tak_dikenal"]:
        print(f"TIDAK dikonversi, dibiarkan apa adanya: {len(lap['tak_dikenal'])} baris")
        for row, sebab in lap["tak_dikenal"][:10]:
            print(f"  {row[3]} | {row[5]} | {sebab}")
    print("\ncontoh 5 baris hasil:")
    for r in rows[:5]:
        print("  " + " | ".join(str(x) for x in r))

    if not tulis:
        print("\nDRY-RUN. Tidak ada yang ditulis. Jalankan lagi dengan --tulis untuk menulis.")
        return

    backup_name = f"Log backup {date.today().isoformat()}"
    existing = [w.title for w in retry(lambda: sh.worksheets())]
    if backup_name in existing:
        print(f"BATAL: tab '{backup_name}' sudah ada. Hapus atau ganti nama dulu.")
        return
    retry(lambda: sh.duplicate_sheet(source_sheet_id=ws.id, new_sheet_name=backup_name))
    print(f"backup dibuat: '{backup_name}'")

    # Penjaga tabrakan: SO masih jalan, karyawan bisa menekan upload kapan saja.
    # Kalau Log bertambah/berubah antara pembacaan dan penulisan, baris baru itu
    # akan tertimpa -- jadi batalkan dan minta dijalankan ulang.
    cek = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))
    if cek != values:
        print("BATAL: Log berubah saat script jalan (ada upload masuk). Jalankan ulang.")
        return

    retry(lambda: ws.batch_clear([f"A2:H{max(len(values), len(rows) + 1) + 10}"]))
    retry(lambda: ws.update(values=rows, range_name="A2", value_input_option="RAW"))
    print(f"selesai. Log sekarang {len(rows)} baris. Backup ada di '{backup_name}'.")


if __name__ == "__main__":
    main()
