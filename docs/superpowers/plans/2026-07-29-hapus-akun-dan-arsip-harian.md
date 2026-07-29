# Hapus Akun + Output Spreadsheet Per Hari — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin bisa menghapus/menonaktifkan akun karyawan dari web, dan output spreadsheet terpisah per hari SO dengan tab arsip semua hari.

**Architecture:** Edge Function `admin-create-user` yang sudah ada mendapat action `deactivate`/`reactivate`; `list` ikut mengembalikan status nonaktif. `Admin.jsx` menambah tombol per baris akun. Sisi spreadsheet murni perubahan rumus (tidak ada kode aplikasi): tab Rekap mendapat kotak tanggal di `G1`, Rekap + Template Olsera difilter ke tanggal itu, dan tab baru **Arsip Harian** menampilkan semua hari — semuanya rumus hidup dari tab Log.

**Tech Stack:** React 18 + Vite, Supabase JS v2, Supabase Edge Function (Deno), Google Sheets API via gspread (Python), Vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-hapus-akun-dan-arsip-harian-design.md`

## Global Constraints

- Tidak ada dependency baru. Teks UI bahasa Indonesia; CSS class yang boleh dipakai: `card`, `row`, `primary`, `secondary`, `error`, `ok`, `muted`, `center`.
- Admin dicek di server, persis `user.email === 'admin@tokokartini.app'`. Cek di frontend hanya kosmetik.
- Error app-level dari Edge Function: HTTP 200 `{ok:false, error:"..."}`. Hanya auth yang 401/403.
- Akun `admin@tokokartini.app` tidak boleh dihapus, dinonaktifkan, atau diaktifkan lewat function.
- Username selalu huruf kecil → email `<username>@tokokartini.app`.
- **Sheet locale `in_ID`**: pemisah argumen rumus `;`, pemisah kolom array `\`. Salin rumus di plan ini **persis**.
- **`Log!A` adalah teks** berformat `YYYY-MM-DD HH:MM:SS` (ditulis `valueInputOption=RAW` oleh `upload-rak`), bukan tipe tanggal — pencocokan tanggal memakai awalan teks.
- Tab **Log** append-only dan satu-satunya sumber data. Script apa pun **dilarang menulis ke Log bila Log sudah berisi data**.
- Test runner `npm test`; build `npm run build`. Jalankan dari root proyek `C:\Users\COMPUTER\Documents\Claude AI\so-kartini`.
- Kredensial Google service account: `C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json`. Sheet id `1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw`.

---

### Task 1: Rumus spreadsheet — filter per hari + tab Arsip Harian

**Files:**
- Modify: `scripts/setup_sheet.py`

**Interfaces:**
- Consumes: tab `Log` kolom `A=Waktu, B=Staff, C=Rak, D=Produk, E=Satuan, F=SKU, G=Qty, H=ED`.
- Produces (dipakai Sopian, bukan task lain): `Rekap!G1` = kotak tanggal; tab `Rekap`, `Template Olsera`, `Arsip Harian` terisi rumus.

- [ ] **Step 1: Ganti konstanta rumus di `scripts/setup_sheet.py`**

Ganti blok `REKAP = [...]` dan `TEMPLATE = (...)` (baris 18–29) dengan:

```python
# Tanggal efektif = Rekap!G1, kosong berarti hari ini.
TGL = 'TEXT(IF($G$1="";TODAY();$G$1);"yyyy-mm-dd")'
TGL_TPL = 'TEXT(IF(Rekap!$G$1="";TODAY();Rekap!$G$1);"yyyy-mm-dd")'

REKAP = [
    f'=IFERROR(SORT(UNIQUE(FILTER(Log!F2:F;Log!F2:F<>"";LEFT(Log!A2:A;10)={TGL})));"")',
    '=ARRAYFORMULA(IF(A2:A="";"";IFERROR(VLOOKUP(A2:A;{Log!F2:F\\Log!D2:D};2;FALSE);"")))',
    '=ARRAYFORMULA(IF(A2:A="";"";IFERROR(VLOOKUP(A2:A;{Log!F2:F\\Log!E2:E};2;FALSE);"")))',
    f'=ARRAYFORMULA(IF(A2:A="";"";SUMIFS(Log!G:G;Log!F:F;A2:A;Log!A:A;{TGL}&"*")))',
]
TEMPLATE = (
    '=IFERROR(QUERY({Log!A2:H};'
    '"select max(Col1), Col4, Col5, Col6, sum(Col7), Col3, max(Col8) '
    'where Col6<>\'\' and Col1 starts with \'"&' + TGL_TPL + '&"\' '
    'group by Col4, Col5, Col6, Col3 '
    'label max(Col1) \'\', sum(Col7) \'\', max(Col8) \'\'";0);"")'
)
# Arsip: semua hari, dikelompokkan per tanggal+SKU, terbaru di atas.
# Col1=LEFT(Log!A;10) tanggal, Col2=Produk, Col3=Satuan, Col4=SKU, Col5=Qty
ARSIP = (
    '=IFERROR(QUERY({ARRAYFORMULA(LEFT(Log!A2:A;10))\\Log!D2:G};'
    '"select Col1, Col4, Col2, Col3, sum(Col5) '
    'where Col4<>\'\' group by Col1, Col4, Col2, Col3 '
    'order by Col1 desc, Col2 label sum(Col5) \'\'";0);"")'
)
```

- [ ] **Step 2: Pastikan zona waktu sheet = Asia/Jakarta**

`TODAY()` memakai zona waktu spreadsheet, bukan zona laptop. Kalau zona sheet masih UTC, "kosong = hari ini" akan meleset 7 jam tiap malam. Di `main()`, ganti blok `updateSpreadsheetProperties` yang hanya menyetel `locale` (baris 60–62) dengan:

```python
    # Locale in_ID menentukan pemisah rumus ';'. Zona waktu menentukan TODAY()
    # — tanpa ini "kosong = hari ini" meleset 7 jam tiap lewat pukul 17:00 WIB.
    retry(lambda: sh.batch_update({"requests": [{
        "updateSpreadsheetProperties": {
            "properties": {"locale": "in_ID", "timeZone": "Asia/Jakarta"},
            "fields": "locale,timeZone",
        }
    }]}))
```

Dan tambahkan pemeriksaan zona waktu tepat setelah `assert` locale yang sudah ada:

```python
    assert props.get("timeZone") == "Asia/Jakarta", f"timeZone bukan Asia/Jakarta: {props.get('timeZone')}"
    print(f"TimeZone verified: {props.get('timeZone')}")
```

- [ ] **Step 3: Tulis kotak tanggal + tab Arsip Harian di `main()`**

Di `main()`, ganti blok "Setup Rekap tab" dan "Setup Template Olsera tab" (baris 74–82) dengan:

```python
    # Setup Rekap tab (+ kotak tanggal di F1/G1)
    rekap = get_or_add_worksheet(sh, "Rekap", rows=3000, cols=8)
    retry(lambda: rekap.update(values=[["SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:D1"))
    retry(lambda: rekap.update(values=[["Tanggal (kosong = hari ini)"]], range_name="F1"))
    retry(lambda: rekap.update(values=[REKAP], range_name="A2:D2", raw=False))

    # Setup Template Olsera tab (kolom A:G tetap bersih untuk di-copy ke Olsera)
    tpl = get_or_add_worksheet(sh, "Template Olsera", rows=3000, cols=8)
    retry(lambda: tpl.update(values=[["time", "product", "variant", "sku", "qty", "rack", "expired_date"]], range_name="A1:G1"))
    retry(lambda: tpl.update(values=[[TEMPLATE]], range_name="A2", raw=False))

    # Setup Arsip Harian tab (semua hari, tidak ikut berganti saat tanggal berganti)
    arsip = get_or_add_worksheet(sh, "Arsip Harian", rows=5000, cols=5)
    retry(lambda: arsip.update(values=[["Tanggal", "SKU", "Produk", "Satuan", "Total Qty"]], range_name="A1:E1"))
    retry(lambda: arsip.update(values=[[ARSIP]], range_name="A2", raw=False))
```

- [ ] **Step 4: Ganti uji-formula supaya tidak pernah menimpa Log berisi data**

Ganti blok uji (baris 84–93, dari komentar `# uji formula` sampai `log.batch_clear`) dengan:

```python
    # Uji formula. Menulis ke Log HANYA bila Log masih kosong — kalau sudah ada
    # data SO, uji dilakukan dengan membaca tanggal yang sudah ada di sana.
    isi_log = retry(lambda: log.get_all_values())
    if len(isi_log) <= 1:
        retry(lambda: log.update(
            values=[[time.strftime("%Y-%m-%d") + " 00:00:00", "tes", "Rak 1", "Produk Uji", "Pcs", "TES-1", 5, ""]],
            range_name="A2:H2"))
        tanggal_uji = time.strftime("%Y-%m-%d")
        bersihkan_log = True
    else:
        tanggal_uji = max(r[0][:10] for r in isi_log[1:] if r and r[0])
        bersihkan_log = False
        print(f"Log berisi {len(isi_log) - 1} baris — uji pakai tanggal {tanggal_uji}, Log tidak disentuh")

    retry(lambda: rekap.update(values=[[tanggal_uji]], range_name="G1"))
    time.sleep(3)

    cek = retry(lambda: rekap.get_values("A2:D2"))
    print(f"Rekap A2:D2: {cek}")
    assert cek and cek[0][0] and cek[0][3], f"formula Rekap gagal: {cek}"
    cek2 = retry(lambda: tpl.get_values("A2:G2"))
    print(f"Template A2:G2: {cek2}")
    assert cek2 and cek2[0][3], f"formula Template gagal: {cek2}"
    cek3 = retry(lambda: arsip.get_values("A2:E2"))
    print(f"Arsip A2:E2: {cek3}")
    assert cek3 and cek3[0][0] == tanggal_uji, f"formula Arsip gagal: {cek3}"

    # kosongkan kotak tanggal -> Rekap & Template ikut tanggal hari ini
    retry(lambda: rekap.batch_clear(["G1"]))
    if bersihkan_log:
        retry(lambda: log.batch_clear(["A2:H2"]))
```

- [ ] **Step 5: Jalankan script terhadap sheet live**

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python setup_sheet.py`

Expected: `Locale verified: in_ID`, `TimeZone verified: Asia/Jakarta`, ketiga baris `Rekap A2:D2` / `Template A2:G2` / `Arsip A2:E2` tercetak berisi data, tanpa AssertionError. Bila Log masih berisi data test 2026-07-27, baris "Log berisi N baris" ikut tercetak dan Log tidak berubah.

**Kalau Log ternyata sudah kosong** (Sopian sudah menghapus data test): script menulis satu baris uji `TES-1` bertanggal hari ini lalu menghapusnya lagi — ini aman dan memang jalur yang dirancang. Laporkan jalur mana yang terpakai.

- [ ] **Step 6: Verifikasi manual tab Arsip Harian tidak ikut kosong**

Run ulang pembacaan tanpa mengubah apa pun:

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\scripts"; python -c "
import gspread, warnings
from google.oauth2.service_account import Credentials
warnings.filterwarnings('ignore')
creds = Credentials.from_service_account_file(r'C:\Users\COMPUTER\Documents\Claude AI\claude-code-powershel-1427d99324cd.json', scopes=['https://www.googleapis.com/auth/spreadsheets'])
sh = gspread.authorize(creds).open_by_key('1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw')
for t in ['Rekap', 'Template Olsera', 'Arsip Harian']:
    print('===', t, sh.worksheet(t).get_values()[:4])
"
```

Expected: dengan `Rekap!G1` kosong dan Log berisi data lama (bukan hari ini), `Rekap` dan `Template Olsera` hanya berisi baris judul, sedangkan `Arsip Harian` **tetap menampilkan** tanggal-tanggal lama. Itulah bukti arsip tidak hilang saat tanggal berganti. Catat hasilnya di laporan.

- [ ] **Step 7: Commit**

```bash
git add scripts/setup_sheet.py
git commit -m "feat: output sheet per hari (kotak tanggal) + tab Arsip Harian"
```

---

### Task 2: Edge Function — action `deactivate` dan `reactivate`

**Files:**
- Modify: `supabase/functions/admin-create-user/index.ts`

**Interfaces:**
- Consumes: header `Authorization: Bearer <JWT>` (dikirim otomatis `supabase.functions.invoke`).
- Produces (dipakai Task 3):
  - `{action:'list'}` → 200 `{ok:true, users:[{email, created_at, banned}]}` — `banned` boolean baru.
  - `{action:'deactivate', username}` → 200 `{ok:true, mode:'deleted'|'banned', username, entries}` atau `{ok:false, error}`.
  - `{action:'reactivate', username}` → 200 `{ok:true, mode:'active', username}` atau `{ok:false, error}`.
  - `{action:'create', ...}` → tidak berubah.

- [ ] **Step 1: Tulis ulang isi `supabase/functions/admin-create-user/index.ts`**

```ts
import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  })

const ADMIN_EMAIL = 'admin@tokokartini.app'
const BAN_SELAMANYA = '876000h' // ~100 tahun

// banned_until ada di respons GoTrue tapi belum ada di tipe User supabase-js.
const nonaktif = (u: unknown) => {
  const until = (u as { banned_until?: string }).banned_until
  return !!until && new Date(until) > new Date()
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
    if (!user) return json({ ok: false, error: 'Unauthorized' }, 401)
    if (user.email !== ADMIN_EMAIL) return json({ ok: false, error: 'Forbidden' }, 403)

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
    const { action, username, password } = await req.json()

    const semuaUser = async () => {
      const { data, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 100 })
      if (error) throw new Error(error.message)
      return data.users
    }

    if (action === 'list') {
      const users = (await semuaUser())
        .map((u) => ({ email: u.email ?? '', created_at: u.created_at, banned: nonaktif(u) }))
        .sort((a, b) => a.email.localeCompare(b.email))
      return json({ ok: true, users })
    }

    if (action === 'create') {
      const uname = String(username ?? '').trim().toLowerCase()
      if (!/^[a-z0-9._-]{2,30}$/.test(uname))
        return json({ ok: false, error: 'Username 2-30 karakter: huruf kecil, angka, titik, strip' })
      const pass = String(password ?? '')
      if (pass.length < 8)
        return json({ ok: false, error: 'Password minimal 8 karakter' })
      const email = `${uname}@tokokartini.app`
      const { error } = await admin.auth.admin.createUser({ email, password: pass, email_confirm: true })
      if (error) {
        const dup = /already|registered|exists/i.test(error.message)
        return json({ ok: false, error: dup ? 'Username sudah dipakai' : error.message })
      }
      return json({ ok: true, username: uname })
    }

    if (action === 'deactivate' || action === 'reactivate') {
      const uname = String(username ?? '').trim().toLowerCase()
      const email = `${uname}@tokokartini.app`
      if (email === ADMIN_EMAIL)
        return json({ ok: false, error: 'Akun admin tidak bisa dihapus atau dinonaktifkan' })
      const target = (await semuaUser()).find((u) => u.email === email)
      if (!target) return json({ ok: false, error: 'Akun tidak ditemukan' })

      if (action === 'reactivate') {
        const { error } = await admin.auth.admin.updateUserById(target.id, { ban_duration: 'none' })
        if (error) return json({ ok: false, error: error.message })
        return json({ ok: true, mode: 'active', username: uname })
      }

      // Entri SO adalah catatan yang harus tetap ada: akun yang sudah pernah
      // input dinonaktifkan, bukan dihapus.
      const { count, error: hitungErr } = await admin
        .from('count_entries')
        .select('id', { count: 'exact', head: true })
        .eq('user_id', target.id)
      if (hitungErr) return json({ ok: false, error: hitungErr.message })

      if (!count) {
        const { error } = await admin.auth.admin.deleteUser(target.id)
        if (error) return json({ ok: false, error: error.message })
        return json({ ok: true, mode: 'deleted', username: uname, entries: 0 })
      }
      const { error } = await admin.auth.admin.updateUserById(target.id, { ban_duration: BAN_SELAMANYA })
      if (error) return json({ ok: false, error: error.message })
      return json({ ok: true, mode: 'banned', username: uname, entries: count })
    }

    return json({ ok: false, error: 'Action tidak dikenal' })
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500)
  }
})
```

- [ ] **Step 2: Verifikasi baca-ulang**

Tidak bisa dijalankan lokal (Deno edge function; deploy ada di Task 4). Verifikasi manual: pastikan (a) urutan auth tidak berubah — `getUser()` dan kedua penjagaan tetap sebelum `req.json()`; (b) tiap cabang `action` selalu `return`; (c) `ADMIN_EMAIL` dijaga di cabang `deactivate`/`reactivate`; (d) tidak ada nilai rahasia yang masuk ke respons.

- [ ] **Step 3: Commit**

```bash
git add supabase/functions/admin-create-user/index.ts
git commit -m "feat: action deactivate/reactivate akun (riwayat SO tetap aman)"
```

---

### Task 3: Halaman admin — tombol hapus/aktifkan akun

**Files:**
- Modify: `src/pages/Admin.jsx`

**Interfaces:**
- Consumes: response Edge Function dari Task 2 (`banned` di `list`; `mode` `deleted`/`banned`/`active`).
- Produces: — (halaman akhir).

- [ ] **Step 1: Tambah state dan handler di `src/pages/Admin.jsx`**

Ganti baris state akun (`const [accounts, setAccounts] = useState([])`) menjadi:

```jsx
  const [accounts, setAccounts] = useState([])
  const [acctErr, setAcctErr] = useState(false)
  const [acctBusy, setAcctBusy] = useState('')
```

Ganti fungsi `loadAccounts` menjadi:

```jsx
  async function loadAccounts() {
    const { data, error } = await supabase.functions.invoke('admin-create-user', { body: { action: 'list' } })
    if (error || !data?.ok) { setAcctErr(true); setAccounts([]) }
    else { setAcctErr(false); setAccounts(data.users) }
  }
```

Tambahkan handler baru tepat setelah `createAccount`:

```jsx
  async function ubahAkun(uname, action) {
    if (
      action === 'deactivate' &&
      !window.confirm(
        `Hapus akun "${uname}"?\n\n` +
          'Kalau akun ini belum pernah input SO, akun dihapus permanen.\n' +
          'Kalau sudah pernah input, akun hanya dinonaktifkan — entri SO-nya tetap tersimpan.',
      )
    ) return
    setAcctBusy(uname)
    setMsg('')
    const { data, error } = await supabase.functions.invoke('admin-create-user', {
      body: { action, username: uname },
    })
    if (error || !data?.ok) setMsg(`err:${data?.error || 'Gagal mengubah akun — coba lagi'}`)
    else if (data.mode === 'deleted') setMsg(`ok:Akun ${uname} dihapus permanen (belum pernah input SO)`)
    else if (data.mode === 'banned') setMsg(`ok:Akun ${uname} dinonaktifkan — ${data.entries} entri SO tetap tersimpan`)
    else setMsg(`ok:Akun ${uname} diaktifkan lagi`)
    await loadAccounts()
    setAcctBusy('')
  }
```

- [ ] **Step 2: Ganti daftar akun di JSX**

Ganti blok `<h2>Akun terdaftar</h2>` beserta `accounts.map(...)` di bawahnya dengan:

```jsx
        <h2>Akun terdaftar</h2>
        {acctErr && <p className="error">Gagal memuat daftar akun — coba muat ulang halaman</p>}
        {!acctErr && accounts.length === 0 && <p className="muted">Belum ada akun</p>}
        {accounts.map((u) => {
          const uname = u.email.split('@')[0]
          const barisAdmin = u.email === 'admin@tokokartini.app'
          return (
            <div className="row" key={u.email}>
              <span>
                {uname}
                {u.banned && <span className="muted"> · nonaktif</span>}
              </span>
              {barisAdmin ? (
                <span className="muted">akun admin</span>
              ) : (
                <button
                  className="secondary"
                  disabled={acctBusy === uname}
                  onClick={() => ubahAkun(uname, u.banned ? 'reactivate' : 'deactivate')}
                >
                  {acctBusy === uname ? '…' : u.banned ? 'Aktifkan' : 'Hapus'}
                </button>
              )}
            </div>
          )
        })}
```

- [ ] **Step 3: Jalankan test dan build**

Run: `npm test` → Expected: 12 lulus (tidak ada test baru di task ini; `adminStats` tidak disentuh).
Run: `npm run build` → Expected: sukses tanpa error.

- [ ] **Step 4: Commit**

```bash
git add src/pages/Admin.jsx
git commit -m "feat: tombol hapus/aktifkan akun di halaman admin"
```

---

### Task 4: Deploy + smoke test

**Files:** — (deploy dan pengujian saja; kalau ada bug, perbaiki di file terkait dan commit)

**Interfaces:**
- Consumes: Task 2 (function), Task 3 (frontend).
- Produces: fitur live di https://tokokartini.github.io.

- [ ] **Step 1: Deploy Edge Function**

Token deploy diberikan controller saat task dijalankan (jangan pernah di-commit).

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"
$env:SUPABASE_ACCESS_TOKEN = "<token dari controller>"
npx supabase functions deploy admin-create-user --project-ref qfqulgkpbjceizrapyom --use-api
```

Expected: `"message":"Deployed Functions."`

- [ ] **Step 2: Smoke test lewat script Node**

Buat `smoke_akun.mjs` di root proyek (file sementara, dihapus di Step 4):

```js
import { createClient } from '@supabase/supabase-js'

const URL = 'https://qfqulgkpbjceizrapyom.supabase.co'
const ANON = 'sb_publishable_HDK2-JqOPUY9lFnjZ9JZYg_GpRxOzkQ'
const log = (ok, msg) => console.log(`${ok ? 'OK  ' : 'FAIL'} ${msg}`)
const inv = (c, body) => c.functions.invoke('admin-create-user', { body })

const admin = createClient(URL, ANON)
const { error: loginErr } = await admin.auth.signInWithPassword({
  email: 'admin@tokokartini.app', password: 'Tokokartini08',
})
log(!loginErr, `login admin${loginErr ? ': ' + loginErr.message : ''}`)

// akun tanpa entri -> terhapus permanen
await inv(admin, { action: 'create', username: 'ujihapus', password: 'UjiSO2026!' })
const { data: del } = await inv(admin, { action: 'deactivate', username: 'ujihapus' })
log(del?.ok && del.mode === 'deleted', `akun tanpa entri dihapus permanen: mode=${del?.mode} ${del?.error || ''}`)
const { data: after } = await inv(admin, { action: 'list' })
log(!after.users.some((u) => u.email.startsWith('ujihapus@')), 'akun ujihapus hilang dari daftar')

// akun 'tes' punya entri SO -> harus dinonaktifkan, bukan dihapus
const { data: ban } = await inv(admin, { action: 'deactivate', username: 'tes' })
log(ban?.ok && ban.mode === 'banned' && ban.entries > 0,
  `akun ber-entri dinonaktifkan: mode=${ban?.mode} entri=${ban?.entries} ${ban?.error || ''}`)
const { data: l2 } = await inv(admin, { action: 'list' })
log(l2.users.find((u) => u.email.startsWith('tes@'))?.banned === true, 'status nonaktif muncul di list')

const banned = createClient(URL, ANON)
const { error: banLogin } = await banned.auth.signInWithPassword({
  email: 'tes@tokokartini.app', password: 'TesSO2026!',
})
log(!!banLogin, `akun nonaktif gagal login: ${banLogin ? 'ya' : 'TIDAK — masih bisa masuk!'}`)

// aktifkan lagi
const { data: re } = await inv(admin, { action: 'reactivate', username: 'tes' })
log(re?.ok, `reactivate: ${re?.mode || re?.error}`)
const back = createClient(URL, ANON)
const { error: backErr } = await back.auth.signInWithPassword({
  email: 'tes@tokokartini.app', password: 'TesSO2026!',
})
log(!backErr, `akun aktif lagi bisa login${backErr ? ': ' + backErr.message : ''}`)

// akun admin dijaga
const { data: self } = await inv(admin, { action: 'deactivate', username: 'admin' })
log(self?.ok === false, `akun admin ditolak: ${self?.error}`)

// non-admin ditolak
const { error: forb } = await inv(back, { action: 'list' })
log(!!forb, `non-admin ditolak: ${forb ? 'ya' : 'TIDAK — celah keamanan!'}`)

process.exit(0)
```

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; node smoke_akun.mjs`
Expected: sembilan baris `OK`. Bila ada `FAIL`, laporkan barisnya dan jangan lanjut ke Step 3.

**Catatan:** kalau data test `count_entries` sudah dihapus Sopian, akun `tes` tidak punya entri lagi dan akan **terhapus permanen**, bukan dinonaktifkan. Kalau itu terjadi, baris "akun ber-entri dinonaktifkan" akan FAIL — bukan bug. Dalam kasus itu: buat akun `ujiban`, sisipkan satu entri milik akun itu lewat service key, lalu ulangi bagian nonaktif. Laporkan penyesuaian yang dilakukan.

- [ ] **Step 3: Push frontend**

```bash
git push origin main
```

Lalu tunggu workflow: `gh run list --limit 1 --json status,conclusion` → Expected `conclusion: success`.

- [ ] **Step 4: Bersihkan file sementara**

```powershell
Remove-Item "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\smoke_akun.mjs"
```

Pastikan `git status --short` bersih (file smoke tidak pernah di-commit).

- [ ] **Step 5: Laporkan**

Laporkan hasil smoke test dan status deploy. Tidak ada commit di task ini kecuali ada perbaikan bug.

---

### Task 5: Perbarui README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Tambah keterangan fitur baru**

Baca `README.md` lebih dulu, lalu tambahkan — dengan gaya dan bahasa yang sudah ada di file itu (Indonesia, ringkas):

1. Halaman admin sekarang juga bisa **menghapus/menonaktifkan akun**: akun yang belum pernah input SO dihapus permanen; akun yang sudah pernah input dinonaktifkan dan entri SO-nya tetap tersimpan; akun `admin` tidak bisa dihapus.
2. Struktur spreadsheet: tab **Log** adalah satu-satunya sumber data dan **tidak boleh dihapus isinya** (baris 1 judul juga jangan dihapus); **Rekap** dan **Template Olsera** menampilkan satu hari mengikuti kotak tanggal di `Rekap!G1` (kosong = hari ini); **Arsip Harian** menampilkan semua hari.
3. Menjalankan `python scripts/setup_sheet.py` aman diulang — script tidak menulis ke Log bila Log sudah berisi data.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — hapus akun, kotak tanggal sheet, tab Arsip Harian"
```
