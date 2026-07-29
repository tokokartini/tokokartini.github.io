# Entri Per Akun — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tiap karyawan hanya melihat, mengubah, menghapus, dan mengirim hitungannya sendiri; dua orang boleh menghitung produk yang sama di rak yang sama dan angkanya dijumlahkan di laporan.

**Architecture:** Tiga perubahan database (indeks unik dilonggarkan jadi per orang, policy update dan delete dikunci ke `auth.uid() = user_id`) plus dua filter satu baris di aplikasi (`useEntries` dan Edge Function `upload-rak`). Policy `read entries` sengaja dibiarkan terbuka supaya dashboard admin tetap utuh. Laporan di spreadsheet tidak diubah — rumusnya sudah menjumlahkan per SKU.

**Tech Stack:** React 18 + Vite, Supabase JS v2 (RLS), Supabase Edge Function (Deno), PostgreSQL, Vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-entri-per-akun-design.md`

## Global Constraints

- **Ada data karyawan sungguhan di database saat ini** (3 entri terbuka milik `ichan` dan `naruto`, belum di-upload). Tidak boleh tersentuh oleh langkah apa pun. Tab Log saat ini berisi **hanya baris judul** (1 baris) — semua pengujian wajib mengembalikannya ke keadaan itu.
- Penjaga sebenarnya adalah RLS, bukan tampilan. Uji penghapusan/pengubahan lintas akun **wajib** lewat client kunci anon yang login, bukan service key (service key melewati RLS sehingga tidak menguji apa pun).
- Akun untuk pengujian harus akun sementara yang dibuat dan dihapus sendiri oleh test. Jangan memakai akun karyawan.
- Tidak ada dependency baru. Teks UI bahasa Indonesia. Test runner `npm test` (12 lulus); build `npm run build`. Jalankan dari root `C:\Users\COMPUTER\Documents\Claude AI\so-kartini`.
- Project Supabase live: `qfqulgkpbjceizrapyom`.

---

### Task 1: Perubahan database — indeks per orang + izin milik sendiri

**Files:**
- Create: `supabase/migration-entri-per-akun.sql`
- Modify: `supabase/schema.sql`

**Interfaces:**
- Consumes: tabel `count_entries` (`rack`, `product_name`, `user_id`, `uploaded_at`).
- Produces (dipakai Task 2 & 3): indeks unik `(rack, product_name, user_id) where uploaded_at is null`; policy `update open entries` dan `delete open entries` yang mensyaratkan `auth.uid() = user_id`.

- [ ] **Step 1: Tulis file migrasi**

Buat `supabase/migration-entri-per-akun.sql`:

```sql
-- Entri jadi milik pribadi tiap karyawan.
--
-- 1) Indeks unik dilonggarkan jadi per orang. Sebelumnya satu entri terbuka per
--    (rak, produk) untuk semua orang — begitu daftar disaring per akun, karyawan
--    kedua tidak melihat entri rekannya, mengisi form, lalu ditolak 23505 tanpa
--    bisa menemukan entri yang menghalanginya. Dengan indeks per orang, keduanya
--    punya entri sendiri dan laporan menjumlahkannya (Rekap/Template/Arsip semua
--    sudah group by SKU + sum qty).
-- 2) Ubah dan hapus dikunci ke milik sendiri.
-- Policy "read entries" sengaja dibiarkan terbuka: dashboard admin membacanya.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).

drop index if exists count_entries_open_unique;
create unique index count_entries_open_unique
  on count_entries (rack, product_name, user_id) where uploaded_at is null;

drop policy if exists "update open entries" on count_entries;
create policy "update open entries" on count_entries
  for update to authenticated
  using (uploaded_at is null and auth.uid() = user_id)
  with check (uploaded_at is null and auth.uid() = user_id);

drop policy if exists "delete open entries" on count_entries;
create policy "delete open entries" on count_entries
  for delete to authenticated
  using (uploaded_at is null and auth.uid() = user_id);
```

- [ ] **Step 2: Samakan `supabase/schema.sql`**

Di `supabase/schema.sql`, ubah **di tempat** (jangan menambah baris duplikat):

- Definisi indeks `count_entries_open_unique` (sekitar baris 36-37) → tambahkan `user_id` sebagai kolom ketiga.
- Policy `update open entries` (sekitar baris 49-50) → tambahkan `and auth.uid() = user_id` pada `using` **dan** `with check`.
- Policy `delete open entries` (sekitar baris 51-52) → tambahkan `and auth.uid() = user_id` pada `using`.

Hasil akhirnya harus setara dengan `schema.sql` lama + migrasi ini.

- [ ] **Step 3: Verifikasi baca-ulang**

Tidak ada yang dijalankan di task ini — penerapan ke database live dilakukan controller di Task 3. Verifikasi manual dan catat hasilnya: (a) `schema.sql` dan migrasi menghasilkan keadaan akhir yang sama; (b) policy `update` punya syarat kepemilikan di `using` **dan** `with check` — `with check` saja tidak mencegah mengubah entri orang lain, `using` saja membolehkan mengoper entri ke `user_id` lain; (c) policy `delete` memakai `using` saja (`with check` tidak berlaku untuk DELETE); (d) `read entries` dan `insert own entries` tidak tersentuh.

- [ ] **Step 4: Commit**

```bash
git add supabase/migration-entri-per-akun.sql supabase/schema.sql
git commit -m "feat: entri jadi milik pribadi — indeks unik per orang + izin ubah/hapus milik sendiri"
```

---

### Task 2: Saring ke akun sendiri di aplikasi dan Edge Function

**Files:**
- Modify: `src/lib/useEntries.js`
- Modify: `supabase/functions/upload-rak/index.ts`

**Interfaces:**
- Consumes: policy dan indeks dari Task 1.
- Produces: `useEntries` hanya mengembalikan entri milik pengguna yang login; `upload-rak` hanya mengklaim entri milik pemanggil.

- [ ] **Step 1: Saring query di `src/lib/useEntries.js`**

Di dalam `useEntries(rack, session)`, ambil id pengguna sekali di atas `refresh`:

```js
  const uid = session.user.id
```

Tambahkan `.eq('user_id', uid)` pada query `refresh` (tepat setelah `.eq('rack', rack)`), dan tambahkan `uid` ke daftar dependency `useCallback` sehingga menjadi `[rack, uid]`. Jangan mengubah bagian lain dari `refresh` — penanganan `error` dan nilai kembaliannya harus tetap seperti sekarang.

Tidak ada perubahan di `src/pages/Count.jsx`: `openEntries`, badge jumlah item, dan pencarian entri saat membuka produk semuanya diturunkan dari `entries`, jadi ikut tersaring sendiri.

- [ ] **Step 2: Saring klaim di `supabase/functions/upload-rak/index.ts`**

Pada query klaim atomik (sekitar baris 64-70), tambahkan satu baris `.eq('user_id', user.id)` di antara `.eq('rack', rack)` dan `.is('uploaded_at', null)`:

```ts
    const { data: entries, error: claimErr } = await admin
      .from('count_entries')
      .update({ uploaded_at: new Date().toISOString() })
      .eq('rack', rack)
      .eq('user_id', user.id)
      .is('uploaded_at', null)
      .select('*')
```

Variabel `user` sudah ada di scope itu — hasil `getUser()` yang dipakai untuk autentikasi di awal function. Jangan mengubah pola rollback maupun klaim atomiknya.

- [ ] **Step 3: Jalankan test dan build**

Run: `npm test` → Expected: 12 lulus (tidak ada test baru; keduanya menyentuh Supabase dan proyek ini hanya menguji fungsi murni — verifikasi live ada di Task 3).
Run: `npm run build` → Expected: sukses tanpa error.

- [ ] **Step 4: Commit**

```bash
git add src/lib/useEntries.js supabase/functions/upload-rak/index.ts
git commit -m "feat: daftar entri dan upload disaring ke akun sendiri"
```

---

### Task 3: Terapkan ke live + smoke test + deploy

**Files:** — (operasional; kalau ada bug, perbaiki di file terkait dan commit)

**Interfaces:**
- Consumes: Task 1 (SQL), Task 2 (aplikasi + function).
- Produces: fitur live di https://tokokartini.github.io.

- [ ] **Step 1: Catat keadaan awal**

Sebelum menyentuh apa pun, catat: jumlah baris tab Log, dan daftar `id` + `username` semua baris `count_entries`. Angka-angka ini dipakai untuk membuktikan di Step 5 bahwa data karyawan tidak berubah.

- [ ] **Step 2: Terapkan migrasi ke database live**

Dilakukan controller (butuh token Supabase). Isi `supabase/migration-entri-per-akun.sql` dijalankan lewat Management API atau Supabase Dashboard → SQL Editor, lalu diverifikasi:

```sql
select policyname, cmd, qual, with_check from pg_policies
where tablename = 'count_entries' order by policyname;
select indexdef from pg_indexes where indexname = 'count_entries_open_unique';
```

Expected: `update open entries` dan `delete open entries` memuat `auth.uid() = user_id`; `indexdef` memuat `rack, product_name, user_id`.

- [ ] **Step 3: Deploy Edge Function**

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"
$env:SUPABASE_ACCESS_TOKEN = "<token dari controller>"
npx supabase functions deploy upload-rak --project-ref qfqulgkpbjceizrapyom --use-api
```

Expected: `"message":"Deployed Functions."`

- [ ] **Step 4: Smoke test dengan dua akun sementara**

Buat `smoke_perakun.mjs` di root proyek (file sementara, dihapus di Step 6). Rak uji sengaja diberi nama mencolok supaya baris uji di tab Log mudah dikenali dan dibersihkan.

```js
import { createClient } from '@supabase/supabase-js'

const URL = 'https://qfqulgkpbjceizrapyom.supabase.co'
const ANON = 'sb_publishable_HDK2-JqOPUY9lFnjZ9JZYg_GpRxOzkQ'
const SERVICE = process.env.SO_SERVICE_KEY
const log = (ok, msg) => console.log(`${ok ? 'OK  ' : 'FAIL'} ${msg}`)
const admin = createClient(URL, SERVICE)

const RAK = 'ZZ Rak Uji'
const PRODUK = 'ZZ Produk Uji Bersama'
const akun = async (nama) => {
  const { data } = await admin.auth.admin.createUser({
    email: `${nama}@tokokartini.app`, password: 'UjiPerAkun2026!', email_confirm: true,
  })
  const c = createClient(URL, ANON)
  await c.auth.signInWithPassword({ email: `${nama}@tokokartini.app`, password: 'UjiPerAkun2026!' })
  return { id: data.user.id, c }
}

const A = await akun('zzujia')
const B = await akun('zzujib')
const entri = (uid, nama) => ({
  user_id: uid, username: nama, rack: RAK, product_name: PRODUK,
  units: [{ sku: 'ZZUJI-1', variant: 'Pcs', mult: 1, qty: 5 }], qty_total: 5,
})

// 1. dua orang, produk sama, rak sama -> dua-duanya boleh
const { data: ea, error: eaErr } = await A.c.from('count_entries').insert(entri(A.id, 'zzujia')).select('id')
const { data: eb, error: ebErr } = await B.c.from('count_entries').insert(entri(B.id, 'zzujib')).select('id')
log(!eaErr && !ebErr && ea?.length === 1 && eb?.length === 1,
  `dua entri produk sama di rak sama diterima${eaErr || ebErr ? ': ' + (eaErr || ebErr).message : ''}`)

// 2. A tidak boleh mengubah / menghapus entri B
const { data: upd } = await A.c.from('count_entries').update({ qty_total: 999 }).eq('id', eb[0].id).select('id')
log(!upd || upd.length === 0, `A ubah entri B ditolak: ${upd?.length ?? 0} baris (harus 0)`)
const { data: del } = await A.c.from('count_entries').delete().eq('id', eb[0].id).select('id')
log(!del || del.length === 0, `A hapus entri B ditolak: ${del?.length ?? 0} baris (harus 0)`)

// 3. daftar milik A hanya berisi entri A
const { data: daftarA } = await A.c.from('count_entries').select('id').eq('rack', RAK).eq('user_id', A.id)
log(daftarA?.length === 1 && daftarA[0].id === ea[0].id, `daftar A hanya entri A: ${daftarA?.length} baris`)

// 4. upload sebagai A hanya mengklaim entri A
const { data: up, error: upErr } = await A.c.functions.invoke('upload-rak', { body: { rack: RAK } })
log(!upErr && up?.uploaded === 1, `upload A mengirim 1 entri: uploaded=${up?.uploaded} ${upErr?.message || ''}`)
const { data: cekB } = await admin.from('count_entries').select('uploaded_at').eq('id', eb[0].id)
log(cekB?.[0]?.uploaded_at === null, `entri B masih terbuka setelah A upload: ${cekB?.[0]?.uploaded_at ?? 'null'}`)

// bersihkan database + akun
await admin.from('count_entries').delete().in('id', [ea[0].id, eb[0].id])
await admin.auth.admin.deleteUser(A.id)
await admin.auth.admin.deleteUser(B.id)
const { data: sisa } = await admin.from('count_entries').select('id,username').eq('rack', RAK)
log((sisa?.length ?? 0) === 0, `entri uji bersih: ${sisa?.length ?? 0} sisa`)

process.exit(0)
```

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; $env:SO_SERVICE_KEY = "<service_role_key dari scripts/config.local.json>"; node smoke_perakun.mjs`

Expected: tujuh baris `OK`. Bila baris "A ubah entri B ditolak" atau "A hapus entri B ditolak" gagal, **hentikan** — policy-nya bocor.

- [ ] **Step 5: Bersihkan baris uji di tab Log dan buktikan data karyawan utuh**

Upload di Step 4 menulis satu baris ke tab Log. Hapus **hanya** baris yang kolom Rak-nya `ZZ Rak Uji`, lalu buktikan:

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python -c "
import json, gspread, warnings, requests
from pathlib import Path
from google.oauth2.service_account import Credentials
warnings.filterwarnings('ignore')
c = json.loads(Path('config.local.json').read_text())
creds = Credentials.from_service_account_file(r'C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json', scopes=['https://www.googleapis.com/auth/spreadsheets'])
sh = gspread.authorize(creds).open_by_key(c['sheet_id'])
log = sh.worksheet('Log')
v = log.get_values()
uji = [i for i, r in enumerate(v, 1) if i > 1 and len(r) > 2 and r[2] == 'ZZ Rak Uji']
for i in reversed(uji):
    log.delete_rows(i)
print('baris uji dihapus:', len(uji), '| sisa baris Log:', len(log.get_values()))
h = {'apikey': c['service_role_key'], 'Authorization': 'Bearer ' + c['service_role_key']}
rows = requests.get(c['supabase_url'] + '/rest/v1/count_entries?select=id,username,rack,qty_total,uploaded_at&order=id', headers=h).json()
print('count_entries:', [(e['id'], e['username'], e['rack'], e['qty_total'], bool(e['uploaded_at'])) for e in rows])
"
```

Expected: sisa baris Log kembali sama dengan angka yang dicatat di Step 1, dan `count_entries` berisi persis entri karyawan yang dicatat di Step 1 — id, username, rak, qty, dan status upload semuanya sama.

- [ ] **Step 6: Push frontend dan bersihkan**

```bash
git push origin main
```

Tunggu: `gh run list --limit 1 --json status,conclusion` → Expected `conclusion: success`.

```powershell
Remove-Item "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\smoke_perakun.mjs"
```

Pastikan `git status --short` bersih.

- [ ] **Step 7: Laporkan**

Laporkan hasil smoke test, perbandingan keadaan awal vs akhir dari Step 1 dan Step 5, serta status deploy.

---

### Task 4: Perbarui README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Tambah keterangan**

Baca `README.md` dulu, lalu tambahkan dengan gaya yang sudah ada (Indonesia, ringkas):

1. Tiap karyawan hanya melihat, mengubah, menghapus, dan meng-upload hitungannya sendiri (dijaga aturan database, bukan cuma tampilan). Admin tetap melihat semua di dashboard.
2. Dua karyawan boleh menghitung produk yang sama di rak yang sama — angkanya dijumlahkan di Rekap/Template/Arsip, dan rinciannya per orang tetap terlihat di kolom Staff tab Log.
3. Peringatan operasional: karena Upload per akun, karyawan yang belum menekan Upload menyisakan entri terbuka yang **hanya dia** yang bisa mengirim. Cek kartu "Progress rak" di dashboard admin (angka "terbuka") sebelum menarik laporan.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — entri dan upload per akun"
```
