# -*- coding: utf-8 -*-
"""Sync tab 'Master Pricelist New' -> tabel products (Supabase SO Kartini).

Pakai: python sync_products.py
Butuh: scripts/config.local.json {"supabase_url": ..., "service_role_key": ...}
"""
import json
import sys
import time
from pathlib import Path

# (kolom SKU, kolom satuan, kolom isi) — isi None = grosir (isi 1)
UNIT_SLOTS = [(28, 6, None), (29, 8, 7), (30, 10, 9), (31, 12, 11)]

SHEET_ID = "1BL34AALlM8tmJn7_z2L_RgTZVGEb4JsUVsnFVDzMyVM"
TAB = "Master Pricelist New"
KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"


def parse_isi(raw):
    s = str(raw).strip()
    if not s or s == "-":
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_rows(vals):
    products, skipped, dupes = [], 0, 0
    seen = set()
    for raw in vals[2:]:
        row = list(raw) + [""] * (32 - len(raw))
        name = row[3].strip()
        if not name or row[0].strip().startswith("==="):
            continue
        units = []
        for order, (sku_i, sat_i, isi_i) in enumerate(UNIT_SLOTS):
            sku = row[sku_i].strip()
            if not sku:
                continue
            satuan = row[sat_i].strip()
            if not satuan:
                skipped += 1
                continue
            isi = 1.0 if isi_i is None else parse_isi(row[isi_i])
            units.append({"sku": sku, "satuan": satuan, "isi": isi, "order": order})
        if not units:
            continue
        isis = [u["isi"] for u in units if u["isi"]]
        base = max(isis) if isis else 1.0
        broken = any(u["isi"] is None for u in units)
        for u in units:
            if u["sku"] in seen:
                dupes += 1
                continue
            seen.add(u["sku"])
            mult = 1.0 if broken or not u["isi"] else base / u["isi"]
            products.append({
                "sku": u["sku"],
                "product_name": name,
                "variant": u["satuan"],
                "mult": round(mult, 4),
                "unit_order": u["order"],
                "category": row[0].strip(),
                "brand": row[2].strip(),
                "active": True,
            })
    return products, skipped, dupes


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(delay)


def fetch_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))
    ws = retry(lambda: sh.worksheet(TAB))
    return retry(lambda: ws.get_all_values())


def sync(products):
    import requests

    cfg = json.loads((Path(__file__).parent / "config.local.json").read_text())
    url, key = cfg["supabase_url"].rstrip("/"), cfg["service_role_key"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    for i in range(0, len(products), 500):
        r = requests.post(
            f"{url}/rest/v1/products?on_conflict=sku",
            headers={**headers, "Prefer": "resolution=merge-duplicates"},
            json=products[i : i + 500],
            timeout=60,
        )
        r.raise_for_status()

    active_skus = []
    offset = 0
    while True:
        r = requests.get(
            f"{url}/rest/v1/products?select=sku&active=eq.true&limit=1000&offset={offset}",
            headers=headers,
            timeout=60,
        )
        r.raise_for_status()
        chunk = r.json()
        active_skus.extend(p["sku"] for p in chunk)
        if len(chunk) < 1000:
            break
        offset += 1000

    missing = sorted(set(active_skus) - {p["sku"] for p in products})
    for i in range(0, len(missing), 100):
        chunk = ",".join(f'"{s}"' for s in missing[i : i + 100])
        r = requests.patch(
            f"{url}/rest/v1/products?sku=in.({chunk})",
            headers=headers,
            json={"active": False},
            timeout=60,
        )
        r.raise_for_status()
    return len(missing)


if __name__ == "__main__":
    vals = fetch_sheet()
    products, skipped, dupes = parse_rows(vals)
    print(f"parsed: {len(products)} SKU, skipped (satuan kosong): {skipped}, duplikat: {dupes}")
    deactivated = sync(products)
    print(f"synced. dinonaktifkan (hilang dari sheet): {deactivated}")
