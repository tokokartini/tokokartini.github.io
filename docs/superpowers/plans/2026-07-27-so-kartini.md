# Stok Opname Kartini — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Web app stok opname Toko Kartini di https://tokokartini.github.io — hitung per rak dengan input multi-satuan, simpan ke Supabase, Upload per rak ke Google Sheet (Log + Rekap + Template Olsera otomatis).

**Architecture:** Salinan so-labelshop dirombak: React+Vite static di GitHub Pages (repo `tokokartini/tokokartini.github.io`), Supabase project `qfqulgkpbjceizrapyom` (Auth username→email internal, tabel products/racks/count_entries, Edge Function `upload-rak` yang menulis ke Google Sheet pakai service account). Rekap & Template Olsera = formula di sheet, bukan kode.

**Tech Stack:** React 18, Vite 6, vite-plugin-pwa, @supabase/supabase-js v2, Vitest, Supabase Edge Functions (Deno), Python 3.12 + gspread (sync & setup sheet).

## Global Constraints

- Nama app: "Stok Opname Kartini"; short name "SO Kartini"; bahasa UI Indonesia.
- Warna: hijau tua `#14532d` (primer), orange `#f97316` (aksen), latar krem `#faf7f0`.
- Beranda: sapaan persis `Halo, {nama}! Semangat ya 🔥`.
- Login pakai **Username** + Password; email internal = `<username>@tokokartini.app` (lowercase, trim).
- Supabase URL: `https://qfqulgkpbjceizrapyom.supabase.co`.
- Master sheet ID `1BL34AALlM8tmJn7_z2L_RgTZVGEb4JsUVsnFVDzMyVM`, tab `Master Pricelist New`; service account key `C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json`, email `point-coffee@claude-code-powershel.iam.gserviceaccount.com`.
- Sheet output baru dibuat service account, locale **id_ID** → separator formula `;`, kolom array `\`. Uji formula di cell coba dulu (pelajaran lama: separator salah merusak ribuan cell).
- TANPA: offline queue, halaman riwayat, export CSV di app.
- Satu produk = satu entri terbuka per rak (partial unique index). Entri terkunci setelah `uploaded_at` terisi.
- Commit tiap task selesai; git identity repo sudah diset (`tokokartini`).
- Tanda tangan commit: akhiri body dengan `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Langkah bertanda **[PERLU USER]** = minta Sopian melakukan/memberi sesuatu; berhenti dan tunggu.

---

### Task 1: Kerangka proyek

**Files:**
- Create: `package.json`, `vite.config.js`, `index.html`, `.gitignore`, `src/main.jsx`, `src/styles.css`, `src/lib/supabase.js`, `src/lib/smoke.test.js`
- Copy: `scripts/make_icons.py` dari `C:\Users\COMPUTER\Documents\Claude AI\so-labelshop\scripts\make_icons.py` (ganti warna ke `#14532d`), hasilkan `public/icon-192.png`, `public/icon-512.png`

**Interfaces:**
- Produces: `supabase` client (`src/lib/supabase.js`), npm scripts `dev/build/test`.

- [ ] **Step 1: Tulis file konfigurasi**

`package.json`:
```json
{
  "name": "so-kartini",
  "type": "module",
  "version": "0.1.0",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2.38.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^6.0.0",
    "vite-plugin-pwa": "^1.3.0",
    "vitest": "^1.0.0"
  }
}
```

`vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  base: '/',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Stok Opname Kartini',
        short_name: 'SO Kartini',
        description: 'Stok opname Toko Kartini',
        theme_color: '#14532d',
        background_color: '#faf7f0',
        display: 'standalone',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  test: { environment: 'node' },
})
```

`index.html`:
```html
<!doctype html>
<html lang="id">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <meta name="theme-color" content="#14532d" />
    <title>Stok Opname Kartini</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`.gitignore`:
```
node_modules
dist
.env.local
scripts/config.local.json
scripts/__pycache__
scripts/.pytest_cache
```

`src/main.jsx`:
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')).render(<App />)
```

`src/lib/supabase.js`:
```js
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)
```

`src/styles.css` — tema lengkap:
```css
:root {
  --green: #14532d;
  --green-dark: #0f3d21;
  --orange: #f97316;
  --cream: #faf7f0;
  --card: #ffffff;
  --text: #1c1917;
  --muted: #78716c;
  --border: #e7e5e4;
  --error: #b91c1c;
  --ok: #15803d;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  background: var(--cream);
  color: var(--text);
}
#root { max-width: 560px; margin: 0 auto; padding: 12px; }
h1 { font-size: 1.25rem; margin: 8px 0 16px; }
h1 .sub { font-size: 0.75rem; color: var(--muted); font-weight: 400; }
.card {
  background: var(--card);
  border-radius: 16px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.08);
}
input, select {
  width: 100%;
  padding: 12px;
  font-size: 1rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #fff;
  margin: 4px 0 12px;
}
button {
  border: 0;
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
}
button.primary { background: var(--green); color: #fff; width: 100%; }
button.primary:disabled { opacity: 0.6; }
button.secondary { background: #f5f5f4; color: var(--text); }
button.link { background: none; color: var(--green); padding: 4px; }
.badge {
  background: var(--orange);
  color: #fff;
  border-radius: 999px;
  padding: 2px 12px;
  font-size: 0.85rem;
  font-weight: 700;
}
.row { display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.error { color: var(--error); font-size: 0.9rem; }
.ok { color: var(--ok); font-size: 0.9rem; }
.center { text-align: center; margin-top: 40vh; color: var(--muted); }
.muted { color: var(--muted); font-size: 0.85rem; }
.entry {
  display: flex; justify-content: space-between; padding: 12px 4px;
  border-bottom: 1px solid var(--border); cursor: pointer;
}
.entry.locked { opacity: 0.55; cursor: default; }
.entry .qty { font-weight: 700; }
.unit-row { display: flex; align-items: center; gap: 8px; }
.unit-row label { flex: 1; }
.unit-row input { width: 110px; text-align: right; margin: 4px 0; }
.total { text-align: center; font-size: 2rem; font-weight: 800; color: var(--orange); margin: 8px 0; }
.actions { display: flex; gap: 8px; }
.actions button { flex: 1; }
```

`src/lib/smoke.test.js`:
```js
import { describe, it, expect } from 'vitest'

describe('smoke', () => {
  it('runs', () => expect(1 + 1).toBe(2))
})
```

- [ ] **Step 2: Install + jalankan test**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; npm install; npm test`
Expected: smoke test PASS. (`App.jsx` belum ada — build belum dites di task ini, hanya vitest.)

- [ ] **Step 3: Ikon PWA**

Copy `make_icons.py` dari repo lama, ganti warna latar jadi `#14532d`, run: `python scripts/make_icons.py` → `public/icon-192.png`, `public/icon-512.png` ada.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: kerangka proyek Vite + tema hijau-orange"
```

---

### Task 2: Schema Supabase + racks awal

**Files:**
- Create: `supabase/schema.sql`

**Interfaces:**
- Produces: tabel `products(sku, product_name, variant, mult, unit_order, category, brand, active)`, `racks(name, sort, active)`, `count_entries(id, user_id, username, rack, product_name, units jsonb, qty_total, expired_date, uploaded_at, created_at, updated_at)`.
- `units` jsonb: array `[{ "sku": "...", "variant": "Krtn (15 Kg)", "mult": 60, "qty": 1 }]`.

- [ ] **Step 1: Tulis schema.sql**

```sql
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom)
create table if not exists products (
  id bigint generated always as identity primary key,
  sku text unique not null,
  product_name text not null,
  variant text not null,
  mult numeric not null default 1,      -- 1 satuan ini = mult satuan dasar
  unit_order int not null default 0,    -- 0 = satuan terbesar (grosir)
  category text not null default '',
  brand text not null default '',
  active boolean not null default true
);

create table if not exists racks (
  id bigint generated always as identity primary key,
  name text unique not null,
  sort int not null default 0,
  active boolean not null default true
);

create table if not exists count_entries (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_id uuid not null references auth.users (id),
  username text not null,
  rack text not null,
  product_name text not null,
  units jsonb not null,
  qty_total numeric not null check (qty_total >= 0),
  expired_date date,
  uploaded_at timestamptz
);

-- satu entri terbuka per produk per rak
create unique index if not exists count_entries_open_unique
  on count_entries (rack, product_name) where uploaded_at is null;
create index if not exists count_entries_rack_idx on count_entries (rack, uploaded_at);

alter table products enable row level security;
alter table racks enable row level security;
alter table count_entries enable row level security;

create policy "read products" on products for select to authenticated using (true);
create policy "read racks" on racks for select to authenticated using (active);
create policy "read entries" on count_entries for select to authenticated using (true);
create policy "insert own entries" on count_entries
  for insert to authenticated with check (auth.uid() = user_id and uploaded_at is null);
create policy "update open entries" on count_entries
  for update to authenticated using (uploaded_at is null) with check (uploaded_at is null);

insert into racks (name, sort) values
  ('Rak 1', 1), ('Rak 2', 2), ('Rak 3', 3), ('Rak 4', 4), ('Rak 5', 5)
on conflict (name) do nothing;
```

- [ ] **Step 2: [PERLU USER] Jalankan di SQL Editor**

Minta Sopian buka Dashboard project baru → SQL Editor → paste isi `supabase/schema.sql` → Run. Konfirmasi "Success".

- [ ] **Step 3: [PERLU USER] Minta 2 kunci**

Dashboard → Project Settings → API: **anon public key** (buat app) dan **service_role key** (buat script sync — rahasia, tidak masuk git).

- [ ] **Step 4: Simpan kunci lokal**

Tulis `.env.local`:
```
VITE_SUPABASE_URL=https://qfqulgkpbjceizrapyom.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key dari user>
```
Tulis `scripts/config.local.json`:
```json
{
  "supabase_url": "https://qfqulgkpbjceizrapyom.supabase.co",
  "service_role_key": "<service role key dari user>"
}
```

- [ ] **Step 5: Commit** (schema saja — dua file kunci ter-gitignore)

```bash
git add supabase/schema.sql && git commit -m "feat: schema products/racks/count_entries + RLS"
```

---

### Task 3: Lib konversi & grouping (TDD)

**Files:**
- Create: `src/lib/convert.js`, `src/lib/convert.test.js`, `src/lib/groupProducts.js`, `src/lib/groupProducts.test.js`

**Interfaces:**
- Produces:
  - `totalQty(units) -> number` — units `[{mult, qty}]`, qty kosong/NaN dihitung 0.
  - `breakdownText(units) -> string` — mis. `"1 Krtn (15 Kg) + 2 Kg"`, hanya qty > 0.
  - `groupProducts(products) -> [{name, category, brand, units: [{sku, variant, mult, unit_order}]}]` — group by `product_name`, units urut `unit_order` naik.
  - `filterGroups(groups, query) -> groups` — cocokkan nama produk ATAU salah satu SKU, case-insensitive; query kosong → [] (tidak menampilkan semua, biar ringan).

- [ ] **Step 1: Tulis test gagal**

`src/lib/convert.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { totalQty, breakdownText } from './convert'

const units = [
  { sku: 'A1', variant: 'Krtn (15 Kg)', mult: 60, qty: 1 },
  { sku: 'A2', variant: 'Kg', mult: 4, qty: 2 },
  { sku: 'A3', variant: '250gr', mult: 1, qty: '' },
]

describe('totalQty', () => {
  it('jumlahkan qty × mult, kosong = 0', () => {
    expect(totalQty(units)).toBe(68)
  })
  it('semua kosong = 0', () => {
    expect(totalQty([{ mult: 60, qty: '' }])).toBe(0)
  })
})

describe('breakdownText', () => {
  it('hanya satuan terisi', () => {
    expect(breakdownText(units)).toBe('1 Krtn (15 Kg) + 2 Kg')
  })
})
```

`src/lib/groupProducts.test.js`:
```js
import { describe, it, expect } from 'vitest'
import { groupProducts, filterGroups } from './groupProducts'

const products = [
  { sku: 'B2', product_name: 'Mentega Simas 15kg', variant: 'Kg', mult: 4, unit_order: 1, category: 'Bahan', brand: 'Simas' },
  { sku: 'B1', product_name: 'Mentega Simas 15kg', variant: 'Krtn (15 Kg)', mult: 60, unit_order: 0, category: 'Bahan', brand: 'Simas' },
  { sku: 'C1', product_name: 'Mika DP 7C', variant: 'Pack', mult: 1, unit_order: 0, category: 'Mika', brand: 'DP' },
]

describe('groupProducts', () => {
  it('group per nama, units urut unit_order', () => {
    const g = groupProducts(products)
    expect(g).toHaveLength(2)
    expect(g[0].units.map((u) => u.sku)).toEqual(['B1', 'B2'])
  })
})

describe('filterGroups', () => {
  const groups = groupProducts(products)
  it('cari nama', () => {
    expect(filterGroups(groups, 'mentega')).toHaveLength(1)
  })
  it('cari sku', () => {
    expect(filterGroups(groups, 'c1')[0].name).toBe('Mika DP 7C')
  })
  it('query kosong = []', () => {
    expect(filterGroups(groups, '  ')).toEqual([])
  })
})
```

- [ ] **Step 2: Run test → FAIL** (`convert`/`groupProducts` belum ada)

Run: `npm test`

- [ ] **Step 3: Implementasi**

`src/lib/convert.js`:
```js
export function totalQty(units) {
  return units.reduce((sum, u) => sum + (Number(u.qty) || 0) * u.mult, 0)
}

export function breakdownText(units) {
  return units
    .filter((u) => (Number(u.qty) || 0) > 0)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}
```

`src/lib/groupProducts.js`:
```js
export function groupProducts(products) {
  const map = new Map()
  for (const p of products) {
    let g = map.get(p.product_name)
    if (!g) {
      g = { name: p.product_name, category: p.category, brand: p.brand, units: [] }
      map.set(p.product_name, g)
    }
    g.units.push({ sku: p.sku, variant: p.variant, mult: Number(p.mult), unit_order: p.unit_order })
  }
  for (const g of map.values()) g.units.sort((a, b) => a.unit_order - b.unit_order)
  return [...map.values()]
}

export function filterGroups(groups, query) {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return groups.filter(
    (g) =>
      g.name.toLowerCase().includes(q) ||
      g.units.some((u) => u.sku.toLowerCase().includes(q)),
  )
}
```

- [ ] **Step 4: Run test → PASS**, lalu commit

```bash
git add src/lib/convert.js src/lib/convert.test.js src/lib/groupProducts.js src/lib/groupProducts.test.js
git commit -m "feat: konversi satuan + grouping produk (TDD)"
```

---

### Task 4: Script sync produk + konversi (TDD)

**Files:**
- Create: `scripts/sync_products.py`, `scripts/test_sync.py`, `scripts/config.example.json`

**Interfaces:**
- Consumes: tab `Master Pricelist New` — kolom (0-index): 0 category, 2 brand, 3 nama; slot satuan `(sku_col, satuan_col, isi_col)` = `(28, 6, None)` grosir (isi=1), `(29, 8, 7)`, `(30, 10, 9)`, `(31, 12, 11)`. `Isi` = banyaknya satuan itu per 1 grosir.
- Produces: baris `products` dengan `mult` (ke satuan dasar) + `unit_order`. Satuan dasar = satuan dengan `isi` terbesar; `mult = isi_dasar / isi_satuan`; isi tak terbaca → `mult = 1`.

- [ ] **Step 1: Tulis test gagal**

`scripts/test_sync.py`:
```python
from sync_products import parse_rows

HEADER = [[""] * 32, [""] * 32]


def row(name, slots):
    """slots: list of (sku_col, satuan_col, isi_col_or_None, sku, satuan, isi)"""
    r = [""] * 32
    r[0], r[2], r[3] = "Kresek", "Taxi", name
    for sku_col, sat_col, isi_col, sku, sat, isi in slots:
        r[sku_col], r[sat_col] = sku, sat
        if isi_col is not None:
            r[isi_col] = isi
    return r


def test_multi_satuan_mult():
    vals = HEADER + [row("Kresek Taxi 15", [
        (28, 6, None, "SKU-BAL", "Bal (20 Ikat)", ""),
        (30, 10, 9, "SKU-IKAT", "Ikat (10 Pack)", "20"),
        (31, 12, 11, "SKU-PACK", "Pack", "200"),
    ])]
    products, skipped, dupes = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-BAL"]["mult"] == 200
    assert by["SKU-IKAT"]["mult"] == 10
    assert by["SKU-PACK"]["mult"] == 1
    assert by["SKU-BAL"]["unit_order"] == 0
    assert by["SKU-PACK"]["unit_order"] == 3


def test_satuan_tunggal():
    vals = HEADER + [row("Mika DP 7C", [(28, 6, None, "SKU-M", "Pack", "")])]
    products, _, _ = parse_rows(vals)
    assert products[0]["mult"] == 1


def test_isi_rusak_fallback_1():
    vals = HEADER + [row("Aneh", [
        (28, 6, None, "SKU-X", "Dus", ""),
        (29, 8, 7, "SKU-Y", "Pcs", "abc"),
    ])]
    products, _, _ = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-X"]["mult"] == 1
    assert by["SKU-Y"]["mult"] == 1


def test_skip_tanpa_satuan_dan_dupe():
    vals = HEADER + [
        row("A", [(28, 6, None, "SKU-1", "", "")]),
        row("B", [(28, 6, None, "SKU-2", "Pack", "")]),
        row("C", [(28, 6, None, "SKU-2", "Pack", "")]),
    ]
    products, skipped, dupes = parse_rows(vals)
    assert len(products) == 1 and skipped == 1 and dupes == 1


def test_angka_indonesia():
    vals = HEADER + [row("D", [
        (28, 6, None, "SKU-G", "Bal", ""),
        (29, 8, 7, "SKU-P", "Pcs", "1.000"),
    ])]
    products, _, _ = parse_rows(vals)
    by = {p["sku"]: p for p in products}
    assert by["SKU-G"]["mult"] == 1000
```

- [ ] **Step 2: Run → FAIL**

Run: `cd scripts; python -m pytest test_sync.py -q`

- [ ] **Step 3: Implementasi**

`scripts/sync_products.py`:
```python
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
```

`scripts/config.example.json`:
```json
{
  "supabase_url": "https://qfqulgkpbjceizrapyom.supabase.co",
  "service_role_key": "ISI-DARI-DASHBOARD"
}
```

- [ ] **Step 4: Run test → PASS**

Run: `cd scripts; python -m pytest test_sync.py -q`

- [ ] **Step 5: Jalankan sync sungguhan** (butuh service_role key dari Task 2)

Run: `cd scripts; python sync_products.py`
Expected: ribuan SKU masuk. Verifikasi cepat via REST: query 1 produk yang punya >1 satuan, cek `mult`/`unit_order` masuk akal.

- [ ] **Step 6: Commit**

```bash
git add scripts/sync_products.py scripts/test_sync.py scripts/config.example.json
git commit -m "feat: sync master -> products dengan konversi satuan (TDD)"
```

---

### Task 5: Login + Beranda + App shell

**Files:**
- Create: `src/pages/Login.jsx`, `src/pages/Home.jsx`, `src/App.jsx`

**Interfaces:**
- Produces: `App` render: session undefined → "Memuat…", null → `Login`, tanpa rak → `Home`, ada rak → `Count` (Task 6). Username = `session.user.email.split('@')[0]`. Rak terpilih disimpan `localStorage['so-rack']`.

- [ ] **Step 1: Implementasi**

`src/pages/Login.jsx`:
```jsx
import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const email = `${username.trim().toLowerCase()}@tokokartini.app`
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError('Username atau password salah')
    setBusy(false)
  }

  return (
    <div className="card">
      <h2>Masuk</h2>
      <form onSubmit={submit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none" required />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Masuk…' : 'Masuk'}</button>
      </form>
      <p className="muted">Belum punya akun? Minta dibuatkan admin.</p>
    </div>
  )
}
```

`src/pages/Home.jsx`:
```jsx
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Home({ username, onStart }) {
  const [racks, setRacks] = useState([])
  const [rack, setRack] = useState(localStorage.getItem('so-rack') || '')

  useEffect(() => {
    supabase
      .from('racks')
      .select('name')
      .eq('active', true)
      .order('sort')
      .then(({ data }) => {
        const names = (data || []).map((r) => r.name)
        setRacks(names)
        if (names.length && !names.includes(rack)) setRack(names[0])
      })
  }, [])

  return (
    <div className="card">
      <div className="row">
        <p>Halo, {username}! Semangat ya 🔥</p>
        <button className="secondary" onClick={() => supabase.auth.signOut()}>Keluar</button>
      </div>
      <label>Rak yang dihitung</label>
      <select value={rack} onChange={(e) => setRack(e.target.value)}>
        {racks.map((r) => <option key={r}>{r}</option>)}
      </select>
      <button className="primary" disabled={!rack} onClick={() => { localStorage.setItem('so-rack', rack); onStart(rack) }}>
        Mulai Hitung
      </button>
    </div>
  )
}
```

`src/App.jsx`:
```jsx
import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Login from './pages/Login'
import Home from './pages/Home'
import Count from './pages/Count'

export default function App() {
  const [session, setSession] = useState(undefined)
  const [rack, setRack] = useState(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  if (session === undefined) return <p className="center">Memuat…</p>

  const username = session?.user?.email?.split('@')[0] || ''

  return (
    <>
      <h1>📦 Stok Opname Kartini <span className="sub">Toko Kartini</span></h1>
      {!session && <Login />}
      {session && !rack && <Home username={username} onStart={setRack} />}
      {session && rack && (
        <Count session={session} username={username} rack={rack} onChangeRack={() => setRack(null)} />
      )}
    </>
  )
}
```

- [ ] **Step 2: Cek build** (Count.jsx belum ada — buat stub sementara agar build jalan)

`src/pages/Count.jsx` stub:
```jsx
export default function Count() { return <p className="center">segera</p> }
```
Run: `npm run build`
Expected: build sukses.

- [ ] **Step 3: Commit**

```bash
git add src/App.jsx src/pages/Login.jsx src/pages/Home.jsx src/pages/Count.jsx
git commit -m "feat: login username + beranda pilih rak"
```

---

### Task 6: Halaman hitung (multi-satuan, edit entri, satu entri per produk per rak)

**Files:**
- Create: `src/lib/useEntries.js`, `src/components/CountForm.jsx`
- Modify: `src/pages/Count.jsx` (ganti stub)

**Interfaces:**
- Consumes: `groupProducts/filterGroups` (Task 3), `totalQty/breakdownText` (Task 3), tabel Task 2.
- Produces:
  - `useEntries(rack)` → `{ entries, saveEntry(group, units, expired, existingId), refresh }`; `entries` = semua entri rak hari-hari ini yang `uploaded_at is null` DITAMBAH yang sudah terupload (terkunci), urut `updated_at` desc.
  - `saveEntry`: `existingId` ada → UPDATE (`units`, `qty_total`, `expired_date`, `username`, `updated_at`); tidak → INSERT. Error unik (23505, race) → refresh lalu lempar error "Sudah ada entri produk ini — buka dari daftar".
  - `CountForm({group, initial, onSave, onCancel})` — input per satuan `<label> ×mult`, ED `<input type="date">`, total besar, Simpan/Batal.

- [ ] **Step 1: Implementasi**

`src/lib/useEntries.js`:
```js
import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'

export function useEntries(rack, session) {
  const [entries, setEntries] = useState([])

  const refresh = useCallback(async () => {
    const { data } = await supabase
      .from('count_entries')
      .select('*')
      .eq('rack', rack)
      .order('updated_at', { ascending: false })
      .limit(300)
    setEntries(data || [])
  }, [rack])

  useEffect(() => { refresh() }, [refresh])

  async function saveEntry(group, units, expired, existingId) {
    const payload = {
      units,
      qty_total: totalQty(units),
      expired_date: expired || null,
      username: session.user.email.split('@')[0],
      updated_at: new Date().toISOString(),
    }
    let error
    if (existingId) {
      ;({ error } = await supabase.from('count_entries').update(payload).eq('id', existingId).is('uploaded_at', null))
    } else {
      ;({ error } = await supabase.from('count_entries').insert({
        ...payload,
        user_id: session.user.id,
        rack,
        product_name: group.name,
      }))
    }
    if (error) {
      await refresh()
      if (error.code === '23505') throw new Error('Sudah ada entri produk ini — buka dari daftar')
      throw new Error('Gagal simpan — cek sinyal, lalu coba lagi')
    }
    await refresh()
  }

  return { entries, saveEntry, refresh }
}
```

`src/components/CountForm.jsx`:
```jsx
import { useState } from 'react'
import { totalQty } from '../lib/convert'

export default function CountForm({ group, initial, onSave, onCancel }) {
  const [units, setUnits] = useState(
    group.units.map((u) => {
      const prev = initial?.units?.find((x) => x.sku === u.sku)
      return { ...u, qty: prev?.qty ?? '' }
    }),
  )
  const [expired, setExpired] = useState(initial?.expired_date || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function setQty(sku, qty) {
    setUnits((us) => us.map((u) => (u.sku === sku ? { ...u, qty } : u)))
  }

  async function save() {
    setBusy(true)
    setError('')
    try {
      await onSave(units.map(({ sku, variant, mult, qty }) => ({ sku, variant, mult, qty: Number(qty) || 0 })), expired)
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  return (
    <div className="card">
      <h3>{group.name}</h3>
      {units.map((u) => (
        <div className="unit-row" key={u.sku}>
          <label>{u.variant} <span className="muted">×{u.mult}</span></label>
          <input type="number" inputMode="numeric" min="0" value={u.qty} onChange={(e) => setQty(u.sku, e.target.value)} />
        </div>
      ))}
      <label>Tanggal ED (opsional)</label>
      <input type="date" value={expired} onChange={(e) => setExpired(e.target.value)} />
      <p className="total">{totalQty(units)}</p>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button className="primary" disabled={busy} onClick={save}>{busy ? 'Menyimpan…' : 'Simpan'}</button>
        <button className="secondary" disabled={busy} onClick={onCancel}>Batal</button>
      </div>
    </div>
  )
}
```

`src/pages/Count.jsx`:
```jsx
import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { groupProducts, filterGroups } from '../lib/groupProducts'
import { useEntries } from '../lib/useEntries'
import CountForm from '../components/CountForm'

export default function Count({ session, username, rack, onChangeRack }) {
  const [groups, setGroups] = useState([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // { group, entry|null }
  const { entries, saveEntry, refresh } = useEntries(rack, session)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    let all = []
    async function load(offset = 0) {
      const { data } = await supabase
        .from('products').select('*').eq('active', true)
        .range(offset, offset + 999)
      all = all.concat(data || [])
      if ((data || []).length === 1000) return load(offset + 1000)
      setGroups(groupProducts(all))
    }
    load()
  }, [])

  const results = useMemo(() => filterGroups(groups, query).slice(0, 20), [groups, query])
  const openEntries = entries.filter((e) => !e.uploaded_at)

  function openGroup(group) {
    const entry = openEntries.find((e) => e.product_name === group.name) || null
    setOpen({ group, entry })
    setQuery('')
  }

  function openFromEntry(entry) {
    if (entry.uploaded_at) return
    const group = groups.find((g) => g.name === entry.product_name)
    if (group) setOpen({ group, entry })
  }

  async function upload() {
    setUploading(true)
    setUploadMsg('')
    const { data, error } = await supabase.functions.invoke('upload-rak', { body: { rack } })
    if (error) setUploadMsg('err:Upload gagal — cek sinyal, coba lagi')
    else setUploadMsg(`ok:${data.uploaded} entri tersinkron ke pusat ✓`)
    await refresh()
    setUploading(false)
  }

  return (
    <>
      <div className="card">
        <div className="row">
          <span>{username} · <b>{rack}</b> <span className="badge">{openEntries.length} item</span></span>
          <button className="secondary" onClick={onChangeRack}>Ganti Rak</button>
        </div>
        {uploadMsg && (
          <p className={uploadMsg.startsWith('ok:') ? 'ok' : 'error'}>{uploadMsg.slice(uploadMsg.indexOf(':') + 1)}</p>
        )}
        <label>Cari produk</label>
        <input placeholder="ketik nama produk…" value={query} onChange={(e) => setQuery(e.target.value)} />
        {results.map((g) => (
          <div className="entry" key={g.name} onClick={() => openGroup(g)}>
            <span>{g.name}</span><span className="muted">{g.units.length} satuan</span>
          </div>
        ))}
        {query.trim() && !results.length && <p className="muted">Tidak ada — cek master / minta sync.</p>}
      </div>

      {open && (
        <CountForm
          group={open.group}
          initial={open.entry}
          onCancel={() => setOpen(null)}
          onSave={async (units, expired) => {
            await saveEntry(open.group, units, expired, open.entry?.id)
            setOpen(null)
          }}
        />
      )}

      <div className="card">
        <h3>Hasil rak ini</h3>
        {!entries.length && <p className="muted">Belum ada.</p>}
        {entries.map((e) => (
          <div className={`entry${e.uploaded_at ? ' locked' : ''}`} key={e.id} onClick={() => openFromEntry(e)}>
            <span>{e.product_name}</span>
            <span className="qty">{Number(e.qty_total)}</span>
          </div>
        ))}
        <button className="primary" disabled={uploading || !openEntries.length} onClick={upload} style={{ marginTop: 12 }}>
          {uploading ? 'Mengirim…' : '⬆️ Upload'}
        </button>
      </div>
    </>
  )
}
```

- [ ] **Step 2: Test + build**

Run: `npm test; npm run build`
Expected: semua PASS, build sukses.

- [ ] **Step 3: Tes manual lokal**

Run: `npm run dev` → buka http://localhost:5173 → login akun tes (dibuat Task 9; kalau belum ada, buat 1 akun tes `tes@tokokartini.app` dulu via Dashboard) → hitung 1 produk 2 satuan → cek total → Simpan → klik entri → ubah qty → Simpan → pastikan tetap 1 baris. Cek row di Supabase Table Editor.

- [ ] **Step 4: Commit**

```bash
git add src/pages/Count.jsx src/components/CountForm.jsx src/lib/useEntries.js
git commit -m "feat: halaman hitung multi-satuan + edit entri per rak"
```

---

### Task 7: Google Sheet output (Log + Rekap + Template Olsera)

**Files:**
- Create: `scripts/setup_sheet.py`

**Interfaces:**
- Produces: spreadsheet baru "SO Toko Kartini" (locale id_ID), ID-nya dicetak & disimpan ke `scripts/config.local.json` key `sheet_id`. Tab:
  - `Log` header: `Waktu | Staff | Rak | Produk | Satuan | SKU | Qty | ED` (A–H). Edge Function append mulai baris 2.
  - `Rekap` header: `SKU | Produk | Satuan | Total Qty`, formula array di baris 2.
  - `Template Olsera` header: `time | product | variant | sku | qty | rack | expired_date`, satu formula FILTER di A2.
- Dibagikan (writer) ke `simaung.coorporate@gmail.com` + email baru user.

- [ ] **Step 1: Implementasi**

`scripts/setup_sheet.py`:
```python
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
```

- [ ] **Step 2: [PERLU USER] Minta email baru user** (buat dibagikan akses sheet)

- [ ] **Step 3: Jalankan**

Run: `cd scripts; python setup_sheet.py <email-baru-user>`
Expected: URL sheet tercetak; assert formula lolos (baris uji otomatis dihapus). Buka sheet, cek 3 tab.

- [ ] **Step 4: Commit**

```bash
git add scripts/setup_sheet.py && git commit -m "feat: setup sheet SO Kartini (Log/Rekap/Template Olsera)"
```

---

### Task 8: Edge Function upload-rak

**Files:**
- Create: `supabase/functions/upload-rak/index.ts`

**Interfaces:**
- Consumes: JWT user (header Authorization, otomatis oleh `supabase.functions.invoke`); body `{ rack: string }`; secrets `GOOGLE_SA_EMAIL`, `GOOGLE_SA_KEY` (private key PEM, `\n` literal boleh), `SHEET_ID`; env bawaan `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`.
- Produces: response `{ uploaded: number }`. Menulis 1 baris Log per satuan ber-qty (`valueInputOption: RAW`), lalu set `uploaded_at`. Waktu WIB `YYYY-MM-DD HH:mm:ss`.

- [ ] **Step 1: Implementasi**

`supabase/functions/upload-rak/index.ts`:
```ts
import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function pemToDer(pem: string): Uint8Array {
  const b64 = pem.replace(/-----[^-]+-----/g, '').replace(/\\n/g, '').replace(/\s/g, '')
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
}

async function googleToken(email: string, key: string): Promise<string> {
  const now = Math.floor(Date.now() / 1000)
  const enc = (o: unknown) =>
    btoa(JSON.stringify(o)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const unsigned = `${enc({ alg: 'RS256', typ: 'JWT' })}.${enc({
    iss: email,
    scope: 'https://www.googleapis.com/auth/spreadsheets',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  })}`
  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8', pemToDer(key), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign'],
  )
  const sig = new Uint8Array(
    await crypto.subtle.sign('RSASSA-PKCS1-v1_5', cryptoKey, new TextEncoder().encode(unsigned)),
  )
  const jwt = `${unsigned}.${btoa(String.fromCharCode(...sig)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
  })
  if (!r.ok) throw new Error(`google token: ${r.status}`)
  return (await r.json()).access_token
}

function wib(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 7 * 3600 * 1000)
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })
  try {
    const auth = req.headers.get('Authorization') ?? ''
    const userClient = createClient(
      Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: auth } } },
    )
    const { data: { user } } = await userClient.auth.getUser()
    if (!user) return new Response('Unauthorized', { status: 401, headers: CORS })

    const { rack } = await req.json()
    if (!rack) return new Response('rack wajib', { status: 400, headers: CORS })

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
    const { data: entries, error } = await admin
      .from('count_entries').select('*').eq('rack', rack).is('uploaded_at', null)
    if (error) throw error
    if (!entries.length) {
      return new Response(JSON.stringify({ uploaded: 0 }), {
        headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const rows: (string | number)[][] = []
    for (const e of entries) {
      for (const u of e.units as { sku: string; variant: string; qty: number }[]) {
        if (!u.qty || u.qty <= 0) continue
        rows.push([wib(e.updated_at), e.username, e.rack, e.product_name, u.variant, u.sku, u.qty, e.expired_date ?? ''])
      }
    }

    if (rows.length) {
      const token = await googleToken(Deno.env.get('GOOGLE_SA_EMAIL')!, Deno.env.get('GOOGLE_SA_KEY')!)
      const sheetId = Deno.env.get('SHEET_ID')!
      const r = await fetch(
        `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/Log!A1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ values: rows }),
        },
      )
      if (!r.ok) throw new Error(`sheets append: ${r.status} ${await r.text()}`)
    }

    const ids = entries.map((e) => e.id)
    const { error: upErr } = await admin
      .from('count_entries').update({ uploaded_at: new Date().toISOString() }).in('id', ids)
    if (upErr) throw upErr

    return new Response(JSON.stringify({ uploaded: entries.length }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    console.error(e)
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
```

- [ ] **Step 2: [PERLU USER] Access token Supabase**

Minta Sopian: https://supabase.com/dashboard/account/tokens → Generate new token → kirim. Simpan HANYA di env session (`$env:SUPABASE_ACCESS_TOKEN`), jangan di file.

- [ ] **Step 3: Deploy + secrets**

```powershell
$env:SUPABASE_ACCESS_TOKEN = "<token>"
npx supabase functions deploy upload-rak --project-ref qfqulgkpbjceizrapyom --use-api
npx supabase secrets set --project-ref qfqulgkpbjceizrapyom GOOGLE_SA_EMAIL="point-coffee@claude-code-powershel.iam.gserviceaccount.com" SHEET_ID="<sheet_id dari Task 7>"
# GOOGLE_SA_KEY: ambil field private_key dari file JSON service account, set via file env supaya newline aman:
# buat scratchpad .env berisi GOOGLE_SA_KEY="-----BEGIN PRIVATE KEY-----\n..." lalu:
npx supabase secrets set --project-ref qfqulgkpbjceizrapyom --env-file <scratchpad>\sa.env
```

- [ ] **Step 4: Tes ujung-ke-ujung**

Dev server (`npm run dev`) → login → hitung 1 produk → Upload → cek: response `{uploaded:1}`, baris muncul di tab Log, Rekap & Template ikut, entri di app jadi terkunci (abu-abu), Upload kedua → `{uploaded:0}`, tidak ada baris dobel.

- [ ] **Step 5: Commit**

```bash
git add supabase/functions/upload-rak/index.ts
git commit -m "feat: edge function upload-rak -> Google Sheet Log"
```

---

### Task 9: Deploy GitHub Pages + akun staff

**Files:**
- Create: `.github/workflows/deploy.yml`, `README.md`

- [ ] **Step 1: Workflow** (identik repo lama)

`.github/workflows/deploy.yml`:
```yaml
name: Deploy
on:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm test
      - run: npm run build
        env:
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

`README.md`:
```markdown
# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Function `upload-rak` → Google Sheet "SO Toko Kartini" (Log/Rekap/Template Olsera).
- Sync produk dari Master Pricelist: `cd scripts; python sync_products.py`.
- Akun staff: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
- Rak: tabel `racks` di Table Editor.
- Spec & plan: `docs/superpowers/`.
```

- [ ] **Step 2: [PERLU USER] Login gh akun tokokartini**

Minta Sopian ketik di prompt: `! gh auth login` → GitHub.com → HTTPS → Login with a web browser → login sebagai `tokokartini`. Lalu verifikasi: `gh auth status`.

- [ ] **Step 3: Buat repo + secrets + Pages + push**

```bash
cd "C:/Users/COMPUTER/Documents/Claude AI/so-kartini"
gh repo create tokokartini/tokokartini.github.io --public --source . --push
gh secret set VITE_SUPABASE_URL --repo tokokartini/tokokartini.github.io --body "https://qfqulgkpbjceizrapyom.supabase.co"
gh secret set VITE_SUPABASE_ANON_KEY --repo tokokartini/tokokartini.github.io --body "<anon key>"
gh api -X POST repos/tokokartini/tokokartini.github.io/pages -f build_type=workflow || gh api -X PUT repos/tokokartini/tokokartini.github.io/pages -f build_type=workflow
```
Tunggu Actions hijau (`gh run watch`), buka https://tokokartini.github.io — halaman login muncul.
Catatan: kalau push pakai credential lama (yahya) tertolak, set `git config credential.username tokokartini` dan pastikan `gh auth switch --user tokokartini`.

- [ ] **Step 4: Auth Supabase: matikan signup publik + akun staff**

[PERLU USER] Dashboard → Authentication → Sign In / Up: Disable new user signups (akun hanya dibuat admin). Lalu buat akun: Authentication → Add user → email `nama@tokokartini.app` + password, centang Auto Confirm. Buat minimal 1 akun tes + akun staff yang dibutuhkan. Kirim daftar username yang dibuat.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yml README.md
git commit -m "feat: deploy workflow + README" && git push
```

---

### Task 10: Tes penerimaan di HP + rapikan

- [ ] **Step 1: [PERLU USER] Checklist tes di HP** (kirim ke Sopian)

1. Buka https://tokokartini.github.io di Chrome HP.
2. Login akun tes → beranda "Halo, tes! Semangat ya 🔥".
3. Pilih rak → Mulai Hitung → cari produk multi-satuan → isi 2 satuan → total benar → Simpan.
4. Cari produk sama → form kebuka dengan angka lama → tambah qty → Simpan → tetap 1 baris di "Hasil rak ini".
5. Upload → pesan sukses → cek Google Sheet: Log ada barisnya, Rekap & Template Olsera ikut.
6. Upload lagi tanpa perubahan → "0 entri" → tidak dobel di Sheet.
7. Mode pesawat → Simpan → muncul error "cek sinyal", angka tidak hilang → matikan mode pesawat → Simpan sukses.

- [ ] **Step 2: Perbaiki temuan tes** (kalau ada), commit per perbaikan.

- [ ] **Step 3: Update memory**

Tulis memory file `so-kartini-webapp.md` (URL, Supabase project, sheet ID, cara sync/akun/deploy, akun gh `tokokartini`) + tambah baris di `MEMORY.md`.

---

## Self-Review (sudah dijalankan)

- Spec coverage: nama/warna/sapaan (T1/T5), username-login (T5), rak dari DB (T2/T5), multi-satuan+konversi (T3/T4/T6), satu-entri-per-produk+edit+kunci (T2/T6), upload per rak idempoten (T8), Sheet 3 tab formula (T7), tanpa offline/riwayat/export (tidak dibangun), deploy tokokartini.github.io (T9), akun oleh admin (T9), error handling (T6/T8/T10), testing (T3/T4/T10). ✓
- Placeholder: nilai kunci/token memang diminta runtime dari user, ditandai [PERLU USER]. ✓
- Konsistensi tipe: `units [{sku,variant,mult,qty}]` konsisten T2/T6/T8; kolom Log A–H konsisten T7/T8; `groupProducts` T3 dipakai T6. ✓
