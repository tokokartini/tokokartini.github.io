# Sync Produk dari Web — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sopian bisa menekan satu tombol di halaman admin untuk menarik barang baru dari Master Pricelist ke app, dan sync itu juga jalan sendiri tiap malam.

**Architecture:** Logika `scripts/sync_products.py` diport ke Edge Function `sync-produk`, dipanggil dua jalur — JWT admin dari tombol, atau service role key dari `pg_cron`. Tiap percobaan dicatat ke tabel baru `sync_runs` yang dibaca halaman admin untuk menampilkan "terakhir sync". Kredensial Google sudah ada di secret; hanya `MASTER_SHEET_ID` yang baru.

**Tech Stack:** React 18 + Vite, Supabase Edge Function (Deno), PostgreSQL + pg_cron + pg_net, Google Sheets API, Vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-sync-produk-design.md`

## Global Constraints

- **Ada data karyawan sungguhan di database live** (entri SO terbuka) dan **tab Log berisi arsip**. Tidak boleh tersentuh langkah apa pun.
- Logika parsing harus **sama persis** dengan `scripts/sync_products.py` — kolom, perhitungan `mult`, aturan lewati dan duplikat. Script Python itu tidak boleh diubah.
- Autentikasi function: JWT user harus `admin@tokokartini.app`, ATAU `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>` persis. Selain itu 401/403.
- Error app-level: HTTP 200 `{ok:false, error}`. Hanya auth yang 401/403.
- Tidak ada dependency baru di frontend. Teks UI bahasa Indonesia. CSS class yang ada: `card`, `row`, `primary`, `secondary`, `error`, `ok`, `muted`, `center`, `entry`, `entry-act`, `qty`, `hapus`, `badge`.
- Test runner `npm test` (14 lulus sekarang); build `npm run build`. Jalankan dari root `C:\Users\COMPUTER\Documents\Claude AI\so-kartini`.
- Project Supabase live: `qfqulgkpbjceizrapyom`. Master Pricelist sheet id: `1BL34AALlM8tmJn7_z2L_RgTZVGEb4JsUVsnFVDzMyVM`, tab `Master Pricelist New`.

---

### Task 1: Tabel `sync_runs`

**Files:**
- Create: `supabase/migration-sync-runs.sql`
- Modify: `supabase/schema.sql`

**Interfaces:**
- Produces (dipakai Task 2 & 3): tabel `sync_runs` dengan kolom `id, ran_at, source, ok, total, added, deactivated, skipped, error`; `select` diizinkan untuk `authenticated`, tanpa policy tulis (hanya service role).

- [ ] **Step 1: Tulis file migrasi**

Buat `supabase/migration-sync-runs.sql`:

```sql
-- Catatan tiap percobaan sync produk dari Master Pricelist.
-- Dibaca halaman admin untuk menampilkan "terakhir sync", dan dipakai melacak
-- kegagalan job malam yang tidak ada yang menunggui.
-- Hanya Edge Function (service role) yang menulis — tidak ada policy tulis.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
create table if not exists sync_runs (
  id bigint generated always as identity primary key,
  ran_at timestamptz not null default now(),
  source text not null,
  ok boolean not null,
  total int not null default 0,
  added int not null default 0,
  deactivated int not null default 0,
  skipped int not null default 0,
  error text
);

create index if not exists sync_runs_ran_at_idx on sync_runs (ran_at desc);

alter table sync_runs enable row level security;

create policy "read sync runs" on sync_runs for select to authenticated using (true);
```

- [ ] **Step 2: Samakan `supabase/schema.sql`**

Tambahkan isi migrasi di atas ke akhir `supabase/schema.sql` (tanpa baris komentar "Jalankan di Supabase Dashboard"), mengikuti gaya penulisan tabel lain di file itu — definisi tabel, indeks, `enable row level security`, lalu policy.

- [ ] **Step 3: Verifikasi baca-ulang**

Tidak ada yang dijalankan di task ini. Verifikasi manual dan catat: (a) `schema.sql` dan migrasi menghasilkan keadaan akhir yang sama; (b) RLS aktif dan hanya ada policy `select` — tidak ada insert/update/delete, sehingga browser tidak bisa memalsukan riwayat sync; (c) tidak ada tabel/policy lain yang tersentuh.

- [ ] **Step 4: Commit**

```bash
git add supabase/migration-sync-runs.sql supabase/schema.sql
git commit -m "feat: tabel sync_runs untuk riwayat sync produk"
```

---

### Task 2: Edge Function `sync-produk`

**Files:**
- Create: `supabase/functions/sync-produk/index.ts`
- Create: `src/lib/parseMaster.js`
- Create: `src/lib/parseMaster.test.js`

**Interfaces:**
- Consumes: tabel `sync_runs` (Task 1); secret `MASTER_SHEET_ID` (dipasang controller di Task 4); secret `GOOGLE_SA_EMAIL`, `GOOGLE_SA_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (sudah terpasang).
- Produces (dipakai Task 3): `POST` tanpa body → 200 `{ok:true, total, added, deactivated, skipped}` atau 200 `{ok:false, error}`.
- Produces (dipakai test): `parseMaster(rows)` dari `src/lib/parseMaster.js` → `{products, skipped, dupes}`.

**Catatan penting:** logika parsing ditulis dua kali — sekali sebagai fungsi murni JS di `src/lib/parseMaster.js` supaya bisa di-unit-test dengan Vitest, dan sekali di dalam function Deno. Duplikasi ini disengaja: Edge Function tidak bisa mengimpor dari `src/`, dan tanpa versi JS-nya logika parsing sama sekali tidak teruji. **Salin isinya persis** — kalau berbeda, testnya jadi menyesatkan. Beri komentar di kedua file yang menyebut file pasangannya.

- [ ] **Step 1: Tulis `src/lib/parseMaster.js`**

Port persis dari `scripts/sync_products.py` baris 12-70. Perhatikan detail yang mudah salah: `parse_isi` membuang titik lalu mengubah koma jadi titik; `isis` hanya mengambil `isi` yang *truthy* (jadi 0 ikut terbuang); `base` adalah `max(isis)` atau 1 kalau kosong; `mult` jadi 1 kalau ada `isi` rusak **atau** `isi` unit itu falsy.

```js
// Parsing Master Pricelist -> daftar produk. Fungsi murni supaya bisa diuji.
// KEMBARAN: supabase/functions/sync-produk/index.ts memuat salinan persis logika
// ini (Edge Function tidak bisa mengimpor dari src/). Ubah keduanya bersamaan.

// (kolom SKU, kolom satuan, kolom isi) — isi null = grosir (isi 1)
const UNIT_SLOTS = [[28, 6, null], [29, 8, 7], [30, 10, 9], [31, 12, 11]]

export function parseIsi(raw) {
  const s = String(raw ?? '').trim()
  if (!s || s === '-') return null
  const n = Number(s.replace(/\./g, '').replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

export function parseMaster(rows) {
  const products = []
  const seen = new Set()
  let skipped = 0
  let dupes = 0
  for (const raw of rows.slice(2)) {
    const row = [...raw]
    while (row.length < 32) row.push('')
    const name = String(row[3] ?? '').trim()
    if (!name || String(row[0] ?? '').trim().startsWith('===')) continue
    const units = []
    UNIT_SLOTS.forEach(([skuI, satI, isiI], order) => {
      const sku = String(row[skuI] ?? '').trim()
      if (!sku) return
      const satuan = String(row[satI] ?? '').trim()
      if (!satuan) { skipped++; return }
      const isi = isiI === null ? 1 : parseIsi(row[isiI])
      units.push({ sku, satuan, isi, order })
    })
    if (!units.length) continue
    const isis = units.map((u) => u.isi).filter(Boolean)
    const base = isis.length ? Math.max(...isis) : 1
    const broken = units.some((u) => u.isi === null)
    for (const u of units) {
      if (seen.has(u.sku)) { dupes++; continue }
      seen.add(u.sku)
      const mult = broken || !u.isi ? 1 : base / u.isi
      products.push({
        sku: u.sku,
        product_name: name,
        variant: u.satuan,
        mult: Math.round(mult * 10000) / 10000,
        unit_order: u.order,
        category: String(row[0] ?? '').trim(),
        brand: String(row[2] ?? '').trim(),
        active: true,
      })
    }
  }
  return { products, skipped, dupes }
}
```

- [ ] **Step 2: Tulis test yang gagal**

Buat `src/lib/parseMaster.test.js`. Fixture meniru bentuk sheet: dua baris pertama diabaikan, kolom 0=kategori, 2=merek, 3=nama, slot satuan di kolom 28/6, 29/8/7, 30/10/9, 31/12/11.

```js
import { describe, it, expect } from 'vitest'
import { parseMaster, parseIsi } from './parseMaster'

const kosong = () => Array(32).fill('')
function baris({ kategori = 'Bahan', merek = 'X', nama = 'Produk', slots = [] }) {
  const r = kosong()
  r[0] = kategori; r[2] = merek; r[3] = nama
  const kolom = [[28, 6, null], [29, 8, 7], [30, 10, 9], [31, 12, 11]]
  slots.forEach(([sku, satuan, isi], i) => {
    const [skuI, satI, isiI] = kolom[i]
    r[skuI] = sku; r[satI] = satuan
    if (isiI !== null && isi !== undefined) r[isiI] = isi
  })
  return r
}
const sheet = (...rows) => [kosong(), kosong(), ...rows]

describe('parseIsi', () => {
  it('buang pemisah ribuan, koma jadi desimal', () => {
    expect(parseIsi('1.200')).toBe(1200)
    expect(parseIsi('2,5')).toBe(2.5)
  })
  it('kosong dan strip jadi null', () => {
    expect(parseIsi('')).toBeNull()
    expect(parseIsi('-')).toBeNull()
    expect(parseIsi('abc')).toBeNull()
  })
})

describe('parseMaster', () => {
  it('hitung mult dari isi terbesar', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'Kresek', slots: [['K-G', 'Bal'], ['K-3', 'Pack', '20']] }),
    ))
    expect(products.map((p) => [p.sku, p.mult, p.unit_order]))
      .toEqual([['K-G', 20, 0], ['K-3', 1, 1]])
  })

  it('satuan kosong dilewati dan dihitung', () => {
    const { products, skipped } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['A-G', ''], ['A-3', 'Pack', '5']] }),
    ))
    expect(skipped).toBe(1)
    expect(products.map((p) => p.sku)).toEqual(['A-3'])
  })

  it('sku duplikat dihitung sekali', () => {
    const { products, dupes } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['SAMA', 'Bal']] }),
      baris({ nama: 'B', slots: [['SAMA', 'Pack', '5']] }),
    ))
    expect(dupes).toBe(1)
    expect(products).toHaveLength(1)
    expect(products[0].product_name).toBe('A')
  })

  it('isi rusak bikin semua mult jadi 1', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['A-G', 'Bal'], ['A-3', 'Pack', '-']] }),
    ))
    expect(products.map((p) => p.mult)).toEqual([1, 1])
  })

  it('baris pemisah === dan baris tanpa nama diabaikan', () => {
    const { products } = parseMaster(sheet(
      baris({ kategori: '=== BAHAN ===', nama: 'Jangan', slots: [['X-1', 'Pcs']] }),
      baris({ nama: '', slots: [['Y-1', 'Pcs']] }),
    ))
    expect(products).toHaveLength(0)
  })

  it('kategori dan merek ikut terbawa', () => {
    const { products } = parseMaster(sheet(
      baris({ kategori: 'Mika', merek: 'DP', nama: 'Mika 7C', slots: [['M-1', 'Pack']] }),
    ))
    expect(products[0]).toMatchObject({ category: 'Mika', brand: 'DP', active: true })
  })
})
```

- [ ] **Step 3: Jalankan test**

Run: `npm test`
Expected: sebelum `parseMaster.js` ada → gagal resolve import. Setelah Step 1 sudah ditulis, semua lulus (14 lama + 8 baru = 22).

Kalau ada yang gagal, **perbaiki `parseMaster.js` agar cocok dengan perilaku Python**, jangan melonggarkan testnya — Python-lah acuannya. Bandingkan langsung dengan `scripts/sync_products.py` baris 12-70 saat ragu.

- [ ] **Step 4: Tulis Edge Function**

Buat `supabase/functions/sync-produk/index.ts`. Salin `pemToDer` dan `googleToken` **apa adanya** dari `supabase/functions/upload-rak/index.ts:8-38`, dan salin logika parsing persis dari `src/lib/parseMaster.js` (beri komentar kembaran seperti di sana).

Kerangka:

```ts
import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })

const ADMIN_EMAIL = 'admin@tokokartini.app'
const TAB = 'Master Pricelist New'

// ... pemToDer + googleToken disalin dari upload-rak ...
// ... UNIT_SLOTS + parseIsi + parseMaster disalin dari src/lib/parseMaster.js ...

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })

  const service = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  const admin = createClient(Deno.env.get('SUPABASE_URL')!, service)
  let source = ''

  try {
    // --- autentikasi dua jalur ---
    const auth = req.headers.get('Authorization') ?? ''
    const token = auth.replace(/^Bearer\s+/i, '')
    if (token && token === service) {
      source = 'jadwal'
    } else {
      const userClient = createClient(
        Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!,
        { global: { headers: { Authorization: auth } } },
      )
      const { data: { user } } = await userClient.auth.getUser()
      if (!user) return json({ ok: false, error: 'Unauthorized' }, 401)
      if (user.email !== ADMIN_EMAIL) return json({ ok: false, error: 'Forbidden' }, 403)
      source = 'manual'
    }

    // --- baca Master Pricelist ---
    const gToken = await googleToken(Deno.env.get('GOOGLE_SA_EMAIL')!, Deno.env.get('GOOGLE_SA_KEY')!)
    const sheetId = Deno.env.get('MASTER_SHEET_ID')!
    const r = await fetch(
      `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/${encodeURIComponent(TAB)}`,
      { headers: { Authorization: `Bearer ${gToken}` } },
    )
    if (!r.ok) throw new Error(`sheets read: ${r.status} ${await r.text()}`)
    const rows: string[][] = (await r.json()).values ?? []

    const { products, skipped } = parseMaster(rows)

    // --- SKU yang sudah ada, untuk hitung "baru" dan menentukan yang dinonaktifkan ---
    const existing: { sku: string; active: boolean }[] = []
    for (let page = 0; page < 20; page++) {
      const { data, error } = await admin.from('products')
        .select('sku, active').range(page * 1000, page * 1000 + 999)
      if (error) throw new Error(error.message)
      existing.push(...data)
      if (data.length < 1000) break
    }
    const adaSku = new Set(existing.map((p) => p.sku))
    const aktifSekarang = existing.filter((p) => p.active).length

    // --- pengaman: jangan pernah menonaktifkan massal karena pembacaan gagal ---
    if (aktifSekarang > 0 && products.length < aktifSekarang / 2) {
      const error = `Dibatalkan: sheet hanya menghasilkan ${products.length} produk, sedangkan sekarang ada ${aktifSekarang} produk aktif. Cek Master Pricelist.`
      await admin.from('sync_runs').insert({ source, ok: false, total: products.length, skipped, error })
      return json({ ok: false, error })
    }

    const added = products.filter((p) => !adaSku.has(p.sku)).length

    // --- upsert bertahap ---
    for (let i = 0; i < products.length; i += 500) {
      const { error } = await admin.from('products')
        .upsert(products.slice(i, i + 500), { onConflict: 'sku' })
      if (error) throw new Error(error.message)
    }

    // --- nonaktifkan SKU aktif yang hilang dari sheet ---
    const diSheet = new Set(products.map((p) => p.sku))
    const hilang = existing.filter((p) => p.active && !diSheet.has(p.sku)).map((p) => p.sku)
    for (let i = 0; i < hilang.length; i += 100) {
      const { error } = await admin.from('products')
        .update({ active: false }).in('sku', hilang.slice(i, i + 100))
      if (error) throw new Error(error.message)
    }

    await admin.from('sync_runs').insert({
      source, ok: true, total: products.length, added, deactivated: hilang.length, skipped,
    })
    return json({ ok: true, total: products.length, added, deactivated: hilang.length, skipped })
  } catch (e) {
    const pesan = String(e)
    if (source) await admin.from('sync_runs').insert({ source, ok: false, error: pesan })
    return json({ ok: false, error: pesan })
  }
})
```

- [ ] **Step 5: Verifikasi baca-ulang**

Function tidak bisa dijalankan lokal; deploy ada di Task 4. Verifikasi manual dan catat: (a) `pemToDer` dan `googleToken` identik dengan `upload-rak`; (b) logika parsing di function identik dengan `src/lib/parseMaster.js` — bandingkan baris per baris; (c) autentikasi jalur service-role dibandingkan dengan **kesamaan string persis**, dan jalur user tetap memeriksa email admin; (d) pengaman massal berjalan **sebelum** upsert maupun penonaktifan; (e) tiap cabang `return`.

- [ ] **Step 6: Commit**

```bash
git add src/lib/parseMaster.js src/lib/parseMaster.test.js supabase/functions/sync-produk/index.ts
git commit -m "feat: edge function sync-produk + parser master yang teruji"
```

---

### Task 3: Kartu Produk di halaman admin

**Files:**
- Modify: `src/pages/Admin.jsx`

**Interfaces:**
- Consumes: tabel `sync_runs` (Task 1), Edge Function `sync-produk` (Task 2).

- [ ] **Step 1: State dan pemuatan riwayat sync**

Tambahkan state di dekat state akun:

```jsx
  const [sync, setSync] = useState(null)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
```

Tambahkan fungsi pemuat, dan panggil di `useEffect` yang sudah ada bersama `load()` dan `loadAccounts()`:

```jsx
  async function loadSync() {
    const { data } = await supabase
      .from('sync_runs').select('*').order('ran_at', { ascending: false }).limit(1)
    setSync(data?.[0] ?? null)
  }
```

- [ ] **Step 2: Handler tombol**

```jsx
  async function syncProduk() {
    setSyncBusy(true)
    setSyncMsg('')
    try {
      const { data, error } = await supabase.functions.invoke('sync-produk', { body: {} })
      if (error || !data?.ok) setSyncMsg(`err:${data?.error || 'Sync gagal — coba lagi'}`)
      else setSyncMsg(`ok:${data.total} produk — ${data.added} baru, ${data.deactivated} dinonaktifkan`)
    } finally {
      await loadSync()
      setSyncBusy(false)
    }
  }
```

- [ ] **Step 3: Kartu Produk di JSX**

Sisipkan sebelum kartu "Kelola akun":

```jsx
      <div className="card">
        <h2>Produk</h2>
        <p className="muted">
          {sync
            ? `terakhir sync: ${jam(sync.ran_at)} (${sync.source}) · ${
                sync.ok
                  ? `${sync.total} produk, ${sync.added} baru, ${sync.deactivated} dinonaktifkan`
                  : `GAGAL — ${sync.error}`
              }`
            : 'belum pernah sync'}
        </p>
        <button className="secondary" disabled={syncBusy} onClick={syncProduk}>
          {syncBusy ? 'Menarik data…' : 'Sync produk'}
        </button>
        {syncMsg && (
          <p className={syncMsg.startsWith('ok:') ? 'ok' : 'error'}>{syncMsg.slice(syncMsg.indexOf(':') + 1)}</p>
        )}
      </div>
```

- [ ] **Step 4: Jalankan test dan build**

Run: `npm test` → Expected: 22 lulus (14 lama + 8 dari Task 2).
Run: `npm run build` → Expected: sukses.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Admin.jsx
git commit -m "feat: kartu Produk di halaman admin — tombol sync + waktu terakhir"
```

---

### Task 4: Terapkan ke live, jadwalkan, smoke test, deploy

**Files:** — (operasional; kalau ada bug, perbaiki di file terkait dan commit)

- [ ] **Step 1: Catat keadaan awal**

Catat: jumlah baris `products` (total dan yang `active`), jumlah baris `count_entries` beserta id dan pemiliknya, dan jumlah baris tab Log. Dipakai membuktikan di Step 6 bahwa data karyawan tidak berubah.

- [ ] **Step 2: Terapkan migrasi + pasang secret**

Dilakukan controller (butuh token Supabase). Jalankan `supabase/migration-sync-runs.sql`, lalu pasang secret `MASTER_SHEET_ID` = `1BL34AALlM8tmJn7_z2L_RgTZVGEb4JsUVsnFVDzMyVM` lewat Management API. Verifikasi tabel `sync_runs` ada dan secret terdaftar (nama saja, jangan cetak nilainya).

- [ ] **Step 3: Deploy function**

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"
$env:SUPABASE_ACCESS_TOKEN = "<token dari controller>"
npx supabase functions deploy sync-produk --project-ref qfqulgkpbjceizrapyom --use-api
```

- [ ] **Step 4: Smoke test**

Buat `smoke_sync.mjs` sementara di root:

```js
import { createClient } from '@supabase/supabase-js'
const URL = 'https://qfqulgkpbjceizrapyom.supabase.co'
const ANON = 'sb_publishable_HDK2-JqOPUY9lFnjZ9JZYg_GpRxOzkQ'
const SERVICE = process.env.SO_SERVICE_KEY
const log = (ok, m) => console.log(`${ok ? 'OK  ' : 'FAIL'} ${m}`)
const admin = createClient(URL, SERVICE)

const hitung = async (filter) => {
  let q = admin.from('products').select('sku', { count: 'exact', head: true })
  if (filter) q = q.eq('active', true)
  const { count } = await q
  return count
}
const sebelumTotal = await hitung(false)
const sebelumAktif = await hitung(true)

// non-admin ditolak
const staf = createClient(URL, ANON)
const { data: made } = await admin.auth.admin.createUser({
  email: 'zzsync@tokokartini.app', password: 'UjiSync2026!', email_confirm: true,
})
await staf.auth.signInWithPassword({ email: 'zzsync@tokokartini.app', password: 'UjiSync2026!' })
const { error: forb } = await staf.functions.invoke('sync-produk', { body: {} })
log(!!forb, `non-admin ditolak: ${forb ? 'ya' : 'TIDAK — celah keamanan!'}`)
await admin.auth.admin.deleteUser(made.user.id)

// admin berhasil
const a = createClient(URL, ANON)
await a.auth.signInWithPassword({ email: 'admin@tokokartini.app', password: 'Tokokartini08' })
const { data: hasil, error: err } = await a.functions.invoke('sync-produk', { body: {} })
log(!err && hasil?.ok, `sync manual berhasil: ${JSON.stringify(hasil)} ${err?.message || ''}`)

const sesudahTotal = await hitung(false)
const sesudahAktif = await hitung(true)
log(sesudahAktif === sebelumAktif,
  `produk aktif tidak berubah: ${sebelumAktif} -> ${sesudahAktif} (master belum diubah, harus sama)`)
log(sesudahTotal === sebelumTotal, `total produk tidak berubah: ${sebelumTotal} -> ${sesudahTotal}`)

const { data: run } = await admin.from('sync_runs').select('*').order('ran_at', { ascending: false }).limit(1)
log(run?.[0]?.ok === true && run[0].source === 'manual', `sync_runs tercatat: ${JSON.stringify(run?.[0])}`)
process.exit(0)
```

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; $env:SO_SERVICE_KEY = "<service_role_key dari scripts/config.local.json>"; node smoke_sync.mjs`

Expected: lima baris `OK`. Kalau "produk aktif tidak berubah" gagal, **hentikan** — berarti parsing hasil port berbeda dari script Python dan katalog berubah tanpa alasan.

- [ ] **Step 5: Pasang penjadwal malam**

Dilakukan controller lewat Management API:

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'sync-produk-harian',
  '0 20 * * *',                        -- 20:00 UTC = 03:00 WIB
  $$
  select net.http_post(
    url := 'https://qfqulgkpbjceizrapyom.supabase.co/functions/v1/sync-produk',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || current_setting('app.service_key', true)
    ),
    body := '{}'::jsonb
  );
  $$
);
```

**Service role key tidak boleh ditulis langsung di definisi job** — definisi job bisa dibaca siapa pun yang punya akses `cron.job`. Simpan lewat `alter database postgres set app.service_key = '<service_role_key>'` lebih dulu, lalu gunakan `current_setting` seperti di atas. Verifikasi dengan `select jobname, schedule, active from cron.job;` dan pastikan hasilnya **tidak** memuat kunci mentah.

- [ ] **Step 6: Uji jalur penjadwal dan buktikan data karyawan utuh**

Jalankan sekali secara manual perintah `net.http_post` yang sama (di luar jadwal), tunggu beberapa detik, lalu periksa `sync_runs` memuat baris baru dengan `source = 'jadwal'` dan `ok = true`.

Lalu bandingkan dengan Step 1: jumlah `products` (total dan aktif), isi `count_entries` (id, pemilik, qty, status upload), dan jumlah baris tab Log harus persis sama.

- [ ] **Step 7: Push dan bersihkan**

```bash
git push origin main
```

Tunggu: `gh run list --limit 1 --json status,conclusion` → Expected `conclusion: success`.

```powershell
Remove-Item "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\smoke_sync.mjs"
```

Pastikan `git status --short` bersih.

- [ ] **Step 8: Laporkan**

Laporkan hasil smoke test, hasil uji jalur penjadwal, perbandingan Step 1 vs Step 6, dan status deploy.

---

### Task 5: Perbarui README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Tambah keterangan**

Baca `README.md` dulu, lalu tambahkan dengan gaya yang ada (Indonesia, ringkas):

1. Barang baru di Master Pricelist masuk ke app lewat tombol **Sync produk** di halaman admin; jalan juga otomatis tiap malam pukul 03:00 WIB.
2. Halaman admin menampilkan waktu sync terakhir beserta ringkasannya, termasuk kalau job malam gagal — cek di situ kalau barang baru belum muncul.
3. `python scripts/sync_products.py` tetap ada sebagai cadangan kalau Edge Function bermasalah.
4. Pengaman: kalau pembacaan sheet menghasilkan kurang dari separuh jumlah produk aktif, sync dibatalkan dan dicatat gagal — supaya sheet yang bermasalah tidak menonaktifkan seluruh katalog.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — sync produk dari halaman admin + jadwal malam"
```
