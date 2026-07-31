# Kolom Rincian Satuan di Log — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tab Log menyimpan satuan asli yang diketik petugas (`2 Krtn + 3 Pack + 5 Pcs`) di samping qty hasil konversi, tanpa mengubah isi tab Rekap, Template Olsera, Arsip Harian, dan Arsip Bulanan.

**Architecture:** Log bertambah dari 8 jadi 9 kolom dengan susunan baru. Alih-alih menulis ulang empat formula QUERY, hanya bagian **sumber** array literal-nya yang diurutkan ulang sehingga nomor `Col1..Col8` di dalam string QUERY tetap menunjuk isi yang sama seperti sekarang. Teks rincian disusun di `rows.ts` dari kolom `units` yang sudah dikirim frontend; tidak ada perubahan di web app maupun tabel `count_entries`.

**Tech Stack:** Deno (Supabase Edge Function), TypeScript, Vitest, Python + gspread, Google Sheets.

## Global Constraints

- Susunan kolom Log final: `A Waktu | B Staff | C Rak | D Produk | E Rincian | F Qty | G Satuan | H ED | I SKU`.
- Qty (F) dan Satuan (G) tetap hasil konversi ke satuan dasar. `totalQty()` di `src/lib/convert.js` tetap satu-satunya penghitung qty dasar — jangan menjumlah ulang di `rows.ts`.
- Format Rincian: ruas `<qty> <variant>` dipisah ` + `, satuan ber-qty 0 dilewati, urut `mult` besar ke kecil, `variant` apa adanya dari master.
- Repo `tokokartini/tokokartini.github.io` **PUBLIK**. Jangan pernah menulis token, password, atau kunci ke file mana pun. `SUPABASE_ACCESS_TOKEN` hanya lewat variabel lingkungan di baris perintah.
- Locale sheet `in_ID`: pemisah argumen formula `;`, pemisah kolom array literal `\`.
- Append Edge Function memakai range terbuka `Log!A1:append` — `index.ts` tidak perlu diubah.
- Task 4 menyentuh sheet dan Edge Function produksi. Jalankan hanya saat tidak ada yang sedang SO.

---

### Task 1: Kolom Rincian di pemilih baris Log

**Files:**
- Modify: `supabase/functions/upload-rak/rows.ts`
- Test: `supabase/functions/upload-rak/rows.test.ts`

**Interfaces:**
- Consumes: `Unit`, `Entry`, `LogRow`, `wib()`, `baseUnitOf()` — semuanya sudah ada di `rows.ts`.
- Produces: `rincianText(units: Unit[] | null): string`. `buildLogRows(entries: Entry[]): { rows: LogRow[]; skipped: string[] }` tetap nama dan tipe yang sama, tetapi tiap baris kini 9 elemen dengan urutan pada Global Constraints.

- [ ] **Step 1: Tulis tes yang gagal untuk `rincianText`**

Tambahkan di `rows.test.ts`, impor `rincianText` di baris import paling atas (`import { baseUnitOf, buildLogRows, rincianText, wib } from './rows.ts'`):

```ts
describe('rincianText', () => {
  it('gabung tiap satuan, urut mult besar ke kecil', () => {
    expect(rincianText(KERTAS.units)).toBe('1 Krtn (50 Pack) + 25 Pack')
  })

  it('urutan units acak tetap keluar besar ke kecil', () => {
    expect(
      rincianText([
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 5 },
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 2 },
        { sku: 'X-2', variant: 'Pack', mult: 5, qty: 3 },
      ]),
    ).toBe('2 Krtn + 3 Pack + 5 Pcs')
  })

  it('satuan qty 0 tidak ikut ditulis', () => {
    expect(
      rincianText([
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 0 },
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 7 },
      ]),
    ).toBe('7 Pcs')
  })

  it('semua qty 0 -> teks kosong', () => {
    expect(
      rincianText([
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 0 },
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 0 },
      ]),
    ).toBe('')
  })

  it('units null atau kosong -> teks kosong', () => {
    expect(rincianText(null)).toBe('')
    expect(rincianText([])).toBe('')
  })

  it('tidak mengubah urutan array aslinya', () => {
    const units = [
      { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 5 },
      { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 2 },
    ]
    rincianText(units)
    expect(units.map((u) => u.sku)).toEqual(['X-3', 'X-G'])
  })
})
```

- [ ] **Step 2: Jalankan tes, pastikan gagal**

Run: `npm test -- rows`
Expected: FAIL — `rincianText is not a function` / gagal di-impor.

- [ ] **Step 3: Tulis `rincianText` di `rows.ts`**

Tambahkan setelah `baseUnitOf`:

```ts
// Rincian satuan asli yang diketik petugas, mis. "2 Krtn + 3 Pack + 5 Pcs".
// Hanya untuk dibaca manusia saat mencocokkan ulang ke rak -- angka yang
// dihitung tab output tetap kolom Qty (satuan dasar), bukan teks ini.
export function rincianText(units: Unit[] | null): string {
  if (!units) return ''
  return [...units]
    .filter((u) => Number(u.qty) > 0)
    .sort((a, b) => b.mult - a.mult)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}
```

- [ ] **Step 4: Jalankan tes, pastikan lulus**

Run: `npm test -- rows`
Expected: blok `rincianText` PASS. Blok `buildLogRows` masih PASS karena belum disentuh.

- [ ] **Step 5: Ubah tes `buildLogRows` ke 9 kolom**

Ganti isi tes yang menyebut posisi kolom. Ganti seluruh blok `describe('buildLogRows', ...)` yang lama dengan:

```ts
describe('buildLogRows', () => {
  it('entri multi-satuan jadi satu baris 9 kolom, rincian + qty dasar', () => {
    const { rows, skipped } = buildLogRows([KERTAS])
    expect(skipped).toEqual([])
    expect(rows).toEqual([
      [
        '2026-07-30 08:01:53',
        'naruto',
        'Rak 5',
        'Kertas Nasi Putih MG 25*27',
        '1 Krtn (50 Pack) + 25 Pack',
        75,
        'Pack',
        '',
        'KTN-0008-3',
      ],
    ])
  })

  it('tanpa mult 1, pakai satuan mult terkecil', () => {
    const { rows } = buildLogRows([
      {
        ...KERTAS,
        units: [
          { sku: 'PKG-0094-G', variant: 'Krtn (20 Trs)', mult: 20, qty: 1 },
          { sku: 'PKG-0094-2', variant: 'Trs', mult: 4, qty: 2 },
        ],
        qty_total: 28,
      },
    ])
    expect(rows[0][4]).toBe('1 Krtn (20 Trs) + 2 Trs')
    expect(rows[0][5]).toBe(28)
    expect(rows[0][6]).toBe('Trs')
    expect(rows[0][8]).toBe('PKG-0094-2')
  })

  it('qty_total 0 tetap ditulis satu baris, rincian kosong', () => {
    const { rows } = buildLogRows([
      { ...KERTAS, units: [{ sku: 'KTN-0008-3', variant: 'Pack', mult: 1, qty: 0 }], qty_total: 0 },
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0][4]).toBe('')
    expect(rows[0][5]).toBe(0)
  })

  it('qty_total null jadi 0, bukan baris hilang', () => {
    const { rows } = buildLogRows([{ ...KERTAS, qty_total: null }])
    expect(rows).toHaveLength(1)
    expect(rows[0][5]).toBe(0)
  })

  it('units kosong atau null dilewati dan dilaporkan', () => {
    const { rows, skipped } = buildLogRows([
      { ...KERTAS, units: [] },
      { ...KERTAS, product_name: 'Tanpa Satuan', units: null },
      KERTAS,
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0][3]).toBe('Kertas Nasi Putih MG 25*27')
    expect(skipped).toEqual(['Kertas Nasi Putih MG 25*27', 'Tanpa Satuan'])
  })

  it('expired_date ditulis apa adanya kalau ada', () => {
    const { rows } = buildLogRows([{ ...KERTAS, expired_date: '2027-01-31' }])
    expect(rows[0][7]).toBe('2027-01-31')
  })

  it('tiap baris tepat 9 kolom', () => {
    const { rows } = buildLogRows([KERTAS])
    expect(rows[0]).toHaveLength(9)
  })

  it('urutan baris sama dengan urutan entri', () => {
    const { rows } = buildLogRows([
      { ...KERTAS, product_name: 'A' },
      { ...KERTAS, product_name: 'B' },
      { ...KERTAS, product_name: 'C' },
    ])
    expect(rows.map((r) => r[3])).toEqual(['A', 'B', 'C'])
  })

  it('entries kosong -> tidak ada baris', () => {
    expect(buildLogRows([])).toEqual({ rows: [], skipped: [] })
  })
})
```

- [ ] **Step 6: Jalankan tes, pastikan gagal**

Run: `npm test -- rows`
Expected: FAIL di blok `buildLogRows` — baris masih 8 kolom dengan urutan lama.

- [ ] **Step 7: Susun 9 kolom di `buildLogRows`**

Ganti komentar kolom dan blok `rows.push` di `rows.ts`:

```ts
// Kolom: Waktu, Staff, rack, Produk, Rincian, Qty, Satuan, ED, SKU -- harus tetap
// 9 dan urutannya persis begitu; Rekap/Template Olsera/Arsip Harian/Arsip Bulanan
// menunjuk kolom ini lewat array literal di scripts/setup_sheet.py.
```

```ts
    rows.push([
      wib(e.updated_at),
      e.username,
      e.rack,
      e.product_name,
      rincianText(e.units),
      Number(e.qty_total ?? 0),
      baseUnit.variant,
      e.expired_date ?? '',
      baseUnit.sku,
    ])
```

Perbarui juga komentar kepala file: satu entri tetap SATU baris, kini dengan kolom Rincian berisi satuan asli.

- [ ] **Step 8: Jalankan seluruh tes**

Run: `npm test`
Expected: semua PASS.

- [ ] **Step 9: Commit**

```bash
git add supabase/functions/upload-rak/rows.ts supabase/functions/upload-rak/rows.test.ts
git commit -m "feat: kolom Rincian satuan asli di tab Log"
```

---

### Task 2: Skrip migrasi kolom Log lama

**Files:**
- Create: `scripts/migrate_log_kolom.py`

**Interfaces:**
- Consumes: `KEY_PATH` dan `SHEET_ID` sama seperti `scripts/convert_log_base_unit.py`; tidak butuh Supabase sama sekali (murni penataan ulang kolom).
- Produces: skrip CLI. `python migrate_log_kolom.py` = dry-run, `--tulis` = backup lalu tulis.

- [ ] **Step 1: Tulis skripnya**

Buat `scripts/migrate_log_kolom.py`:

```python
# -*- coding: utf-8 -*-
"""Tata ulang kolom tab 'Log': 8 kolom lama -> 9 kolom baru.

Lama: Waktu Staff Rak Produk Satuan SKU Qty ED
Baru: Waktu Staff Rak Produk Rincian Qty Satuan ED SKU

Kolom Rincian dikosongkan untuk baris lama -- riwayat sebelum perubahan ini
memang tidak menyimpan satuan asli yang diketik petugas.

Pakai:
  python migrate_log_kolom.py            # dry-run, cuma laporan
  python migrate_log_kolom.py --tulis    # backup tab Log lalu tulis ulang

Tab output tidak disentuh; formula-nya diperbarui terpisah oleh
setup_sheet.py dan add_arsip_bulanan.py. Rekap!G1 juga tidak disentuh.
"""
import sys
import time
import warnings
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_PATH = r"C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"
TAB = "Log"
HEADER_LAMA = ["Waktu", "Staff", "Rak", "Produk", "Satuan", "SKU", "Qty", "ED"]
HEADER_BARU = ["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"]


def retry(fn, tries=6, delay=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"retry {i + 1}: {type(e).__name__}", file=sys.stderr)
            time.sleep(delay)


def pindah(values):
    """values = get_all_values() termasuk header. Balikkan (baris_baru, jumlah)."""
    rows = []
    for raw in values[1:]:
        row = list(raw) + [""] * (8 - len(raw))
        waktu, staff, rack, produk, satuan, sku, qty, ed = row[:8]
        if not str(produk).strip():
            continue
        rows.append([waktu, staff, rack, produk, "", qty, satuan, ed, sku])
    return rows


def main():
    tulis = "--tulis" in sys.argv

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = retry(lambda: gc.open_by_key(SHEET_ID))
    ws = retry(lambda: sh.worksheet(TAB))
    if ws.col_count < 9:
        retry(lambda: ws.resize(rows=ws.row_count, cols=9))

    values = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))

    # Penjaga: kalau header sudah 9 kolom, migrasi pernah jalan. Menjalankannya
    # dua kali akan menggeser kolom untuk kedua kalinya dan merusak datanya.
    header = (values[0] if values else [])[:9]
    if header[:9] == HEADER_BARU:
        print("BATAL: header Log sudah susunan baru, migrasi tidak perlu diulang.")
        return
    if header[:8] != HEADER_LAMA:
        print(f"BATAL: header Log tak dikenali: {header}")
        return

    rows = pindah(values)
    print(f"Log: {len(values) - 1} baris -> {len(rows)} baris")
    print("\ncontoh 5 baris hasil:")
    for r in rows[:5]:
        print("  " + " | ".join(str(x) for x in r))

    if not tulis:
        print("\nDRY-RUN. Tidak ada yang ditulis. Jalankan lagi dengan --tulis untuk menulis.")
        return

    backup_name = f"Log backup kolom {date.today().isoformat()}"
    existing = [w.title for w in retry(lambda: sh.worksheets())]
    if backup_name in existing:
        print(f"BATAL: tab '{backup_name}' sudah ada. Hapus atau ganti nama dulu.")
        return
    retry(lambda: sh.duplicate_sheet(source_sheet_id=ws.id, new_sheet_name=backup_name))
    print(f"backup dibuat: '{backup_name}'")

    # Penjaga tabrakan: kalau ada upload masuk antara pembacaan dan penulisan,
    # baris itu akan tertimpa -- batalkan dan minta dijalankan ulang.
    cek = retry(lambda: ws.get_all_values(value_render_option="UNFORMATTED_VALUE"))
    if cek != values:
        print("BATAL: Log berubah saat script jalan (ada upload masuk). Jalankan ulang.")
        return

    retry(lambda: ws.batch_clear([f"A1:I{max(len(values), len(rows) + 1) + 10}"]))
    retry(lambda: ws.update(values=[HEADER_BARU] + rows, range_name="A1", value_input_option="RAW"))
    print(f"selesai. Log sekarang {len(rows)} baris, 9 kolom. Backup ada di '{backup_name}'.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Jalankan dry-run**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python migrate_log_kolom.py`
Expected: laporan `Log: 217 baris -> 217 baris` dan 5 contoh baris dengan kolom kelima kosong, qty di kolom keenam, satuan ketujuh, SKU terakhir. Tidak ada yang ditulis.

- [ ] **Step 3: Jalankan lagi untuk memastikan dry-run tidak mengubah apa pun**

Run: `python migrate_log_kolom.py`
Expected: laporan identik dengan Step 2 — bukti tidak ada efek samping.

- [ ] **Step 4: Kunci skrip konversi lama supaya tidak merusak Log baru**

`scripts/convert_log_base_unit.py` menulis ulang Log dengan asumsi 8 kolom. Setelah migrasi, menjalankannya akan mengembalikan Log ke susunan lama dan membuang kolom Rincian. Tambahkan penjaga di `main()`, tepat setelah baris `values = retry(lambda: ws.get_all_values(...))`:

```python
    # Log sudah pindah ke susunan 9 kolom (lihat scripts/migrate_log_kolom.py).
    # Skrip ini menulis 8 kolom dengan urutan lama, jadi menjalankannya sekarang
    # akan membuang kolom Rincian dan menggeser Qty/Satuan/SKU. Disimpan hanya
    # sebagai catatan konversi 2026-07-30.
    if (values[0] if values else [])[:5] == ["Waktu", "Staff", "Rak", "Produk", "Rincian"]:
        print("BATAL: Log sudah susunan 9 kolom. Skrip ini hanya untuk format lama.")
        return
```

- [ ] **Step 5: Uji penjaga itu benar-benar menahan**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python convert_log_base_unit.py`
Expected sebelum migrasi dijalankan (Task 4): skrip berjalan seperti biasa dan berhenti di `DRY-RUN`. Sesudah Task 4 Step 1, perintah yang sama harus mencetak `BATAL: Log sudah susunan 9 kolom.` — periksa ulang di titik itu.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_log_kolom.py scripts/convert_log_base_unit.py
git commit -m "feat: skrip migrasi kolom Log ke susunan 9 kolom"
```

---

### Task 3: Geser sumber kolom di keempat formula

**Files:**
- Modify: `scripts/setup_sheet.py`
- Modify: `scripts/add_arsip_bulanan.py`

**Interfaces:**
- Consumes: susunan Log 9 kolom dari Task 1 dan Task 2.
- Produces: konstanta `LOG_TAIL` di `setup_sheet.py` — potongan array literal `Satuan, SKU, Qty` yang sudah diurutkan ulang, dipakai `LOG_SRC`, `ARSIP`, dan `ARSIP_BULANAN`.

Kuncinya: string QUERY tidak diubah sama sekali. Array literal disusun ulang supaya `Col5=Satuan`, `Col6=SKU`, `Col7=Qty`, `Col8=ED` tetap menunjuk isi yang sama seperti sebelum Log berubah.

- [ ] **Step 1: Ganti sumber array literal di `setup_sheet.py`**

Ganti definisi `LOG_SRC` dan tambahkan `LOG_TAIL` tepat sebelumnya:

```python
# Log kini 9 kolom: A Waktu, B Staff, C Rak, D Produk, E Rincian, F Qty,
# G Satuan, H ED, I SKU. Array literal di bawah SENGAJA menyusun ulang kolom
# jadi Satuan, SKU, Qty supaya nomor Col di dalam string QUERY tetap sama
# seperti sebelum kolom Rincian ada -- jadi tidak ada query yang perlu diedit.
# Kolom E (Rincian) tidak ikut: teks itu untuk dibaca manusia di Log saja.
LOG_TAIL = 'Log!G2:G\\Log!I2:I\\Log!F2:F'

LOG_SRC = '{Log!A2:B\\' + RACK_OLSERA + '\\' + PRODUK_STOK + '\\' + LOG_TAIL + '\\Log!H2:H}'
```

- [ ] **Step 2: Ganti sumber `ARSIP` dan `ARSIP_BULANAN` di `setup_sheet.py`**

Pada `ARSIP`, ganti `'\\Log!E2:G};'` menjadi `'\\' + LOG_TAIL + '};'`. Lakukan hal yang sama pada `ARSIP_BULANAN`. Setelah diganti keduanya berbunyi:

```python
ARSIP = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;10))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)
ARSIP_BULANAN = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;7))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)
```

- [ ] **Step 3: Perbarui header Log dan baris uji di `setup_sheet.py`**

Header:

```python
    retry(lambda: log.update(values=[["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"]], range_name="A1:I1"))
```

Baris uji (dipakai hanya kalau Log masih kosong) dan pembersihannya:

```python
        retry(lambda: log.update(
            values=[[time.strftime("%Y-%m-%d") + " 00:00:00", "tes", "Rak 1", "Produk Uji",
                     "1 Pcs", 5, "Pcs", "", "TES-1"]],
            range_name="A2:I2"))
```

```python
        retry(lambda: log.batch_clear(["A2:I2"]))
```

- [ ] **Step 4: Samakan `add_arsip_bulanan.py`**

Ganti konstanta formula di `scripts/add_arsip_bulanan.py` agar memakai sumber yang sama:

```python
# Log 9 kolom: kolom disusun ulang jadi Satuan, SKU, Qty supaya nomor Col di
# string QUERY tetap sama seperti versi Log 8 kolom. Sama persis dengan
# LOG_TAIL di setup_sheet.py -- kalau salah satu berubah, ubah keduanya.
LOG_TAIL = 'Log!G2:G\\Log!I2:I\\Log!F2:F'

ARSIP_BULANAN = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;7))\\' + PRODUK_STOK + '\\' + LOG_TAIL + '};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)
```

- [ ] **Step 5: Periksa tidak ada rujukan kolom lama yang tertinggal**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; git grep -n "Log!E2:G\|Log!E2:H\|A2:H2\|A1:H1" -- scripts/`
Expected: tidak ada hasil.

- [ ] **Step 6: Commit**

```bash
git add scripts/setup_sheet.py scripts/add_arsip_bulanan.py
git commit -m "refactor: sumber formula ikut susunan Log 9 kolom"
```

---

### Task 4: Migrasi sheet, deploy, dan uji ujung ke ujung

**Files:** tidak ada perubahan kode. Task ini menjalankan hasil Task 1–3 ke produksi.

**Interfaces:**
- Consumes: `scripts/migrate_log_kolom.py` (Task 2), `scripts/add_arsip_bulanan.py` dan `scripts/setup_sheet.py` (Task 3), `rows.ts` (Task 1).
- Produces: sheet dan Edge Function produksi dengan susunan 9 kolom.

**Prasyarat:** tidak ada yang sedang SO, dan `SUPABASE_ACCESS_TOKEN` tersedia. Langkah 1 dan 2 di bawah membuat sheet berformat baru sementara Edge Function lama masih menulis 8 kolom — jangan mulai kalau deploy tidak bisa langsung menyusul.

- [ ] **Step 1: Migrasi kolom Log**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python migrate_log_kolom.py --tulis`
Expected: `backup dibuat: 'Log backup kolom 2026-07-31'` lalu `selesai. Log sekarang 217 baris, 9 kolom.`
Kalau keluar `BATAL: Log berubah saat script jalan`, ada yang upload — ulangi dari awal.

- [ ] **Step 2: Pasang formula baru**

Run: `python add_arsip_bulanan.py`
Expected: `Arsip Bulanan formula verified [OK]` dan contoh barisnya berisi bulan, SKU, produk, satuan, qty yang masuk akal.

Lalu buka sheet dan periksa tab Rekap, Template Olsera, dan Arsip Harian masih memakai formula lama yang menunjuk `Log!E2:H`. Perbarui ketiganya:

Run: `python setup_sheet.py`
Expected: `Rekap formula verified [OK]`, `Template formula verified [OK]`, dan cetakan `Arsip Bulanan A2:E2` yang bulannya cocok.
Catatan: skrip ini mengosongkan `Rekap!G1` — itulah sebabnya Task 4 hanya boleh jalan di luar jam SO.

- [ ] **Step 3: Deploy Edge Function**

Token hanya lewat variabel lingkungan, tidak pernah masuk file:

```powershell
$env:SUPABASE_ACCESS_TOKEN = "<token>"
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"
npx supabase functions deploy upload-rak --project-ref qfqulgkpbjceizrapyom --use-api
```

Expected: deploy sukses tanpa error.

- [ ] **Step 4: Uji ujung ke ujung dari web app**

Minta Sopian (atau pakai akun uji) membuka https://tokokartini.github.io, masukkan satu produk multi-satuan di satu rak dengan dua satuan terisi, lalu upload.

Expected di tab Log, baris paling bawah:
- kolom E berisi teks seperti `1 Krtn (50 Pack) + 25 Pack`
- kolom F angka qty dasar, kolom G nama satuan dasar, kolom I SKU
Expected di tab Rekap: SKU itu muncul dengan Total Qty sama dengan kolom F.

- [ ] **Step 5: Bersihkan baris uji dan commit catatan**

Hapus baris uji dari tab Log lewat sheet, lalu:

```bash
git add -A
git commit -m "chore: catat migrasi Log 9 kolom selesai"
```

Kalau tidak ada perubahan file, lewati commit-nya.

- [ ] **Step 6: Cabut token Supabase**

Buka Supabase Dashboard → Account → Access Tokens, cabut token yang dipakai di Step 3. Token itu sudah tersimpan di log sesi, jadi perlakukan sebagai terbakar sekali pakai.

---

## Catatan untuk pelaksana

Kalau Task 4 Step 2 memperlihatkan Rekap kosong atau `#REF!`, jangan menambal formulanya di sheet. Periksa dulu susunan `LOG_TAIL`: `Log!G2:G` harus Satuan, `Log!I2:I` harus SKU, `Log!F2:F` harus Qty. Salah urut di situ akan tampak sebagai qty berisi teks satuan.
