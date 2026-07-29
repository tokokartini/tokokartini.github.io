# Halaman Admin (Dashboard + Kelola Akun) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Akun `admin` login → halaman admin (progress rak, aktivitas karyawan, entri terbaru, form bikin akun karyawan); alur SO karyawan tidak berubah.

**Architecture:** `App.jsx` cabang `username === 'admin'` → render `Admin.jsx`. Dashboard baca `count_entries` + `racks` langsung (RLS read sudah ada), direkap oleh helper murni `src/lib/adminStats.js`. Pembuatan/daftar akun lewat Edge Function baru `admin-create-user` (verifikasi JWT → hanya `admin@tokokartini.app` → aksi pakai service role key).

**Tech Stack:** React 18 + Vite, Supabase JS v2, Supabase Edge Function (Deno), Vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-admin-dashboard-design.md`

## Global Constraints

- Semua teks UI bahasa Indonesia; gaya mengikuti halaman lain (`className`: `card`, `row`, `primary`, `secondary`, `error`, `ok`, `muted`, `center`).
- Tidak ada dependency baru.
- Username selalu dipaksa huruf kecil → email `<username>@tokokartini.app` (konsisten `Login.jsx:14`).
- Admin = email `user.email === 'admin@tokokartini.app'` persis — cek di server (Edge Function); cek frontend hanya kosmetik.
- Password minimal 8 karakter (validasi form DAN server).
- Waktu tampil dalam WIB (`timeZone: 'Asia/Jakarta'`).
- Edge Function app-level error balas HTTP 200 `{ok:false, error:"..."}`; hanya auth yang 401/403 (menyederhanakan penanganan `functions.invoke` di frontend).
- Test runner: `npm test` (vitest run). Jalankan dari root proyek `C:\Users\COMPUTER\Documents\Claude AI\so-kartini`.

---

### Task 1: Helper rekap dashboard (`adminStats.js`)

**Files:**
- Create: `src/lib/adminStats.js`
- Test: `src/lib/adminStats.test.js`

**Interfaces:**
- Consumes: — (murni; input array hasil query Supabase)
- Produces (dipakai Task 3):
  - `rackProgress(entries, rackNames)` → `[{rack, open, uploaded, lastAt}]` urut sesuai `rackNames`; rak tanpa entri: `{open: 0, uploaded: 0, lastAt: null}`.
  - `staffActivity(entries, now = new Date())` → `[{username, today, total, lastAt}]` urut `lastAt` terbaru dulu; `today` = jumlah entri yang tanggal WIB-nya sama dengan tanggal WIB `now`.
  - `latestEntries(entries, n = 20)` → n entri terbaru urut `created_at` desc.
  - `entries` = array `{username, rack, product_name, qty_total, created_at, uploaded_at}`.

- [ ] **Step 1: Tulis test yang gagal**

Buat `src/lib/adminStats.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { rackProgress, staffActivity, latestEntries } from './adminStats'

// created_at UTC; 2026-07-28T18:00Z = 2026-07-29 01:00 WIB
const entries = [
  { username: 'sari', rack: 'Rak 1', product_name: 'Mika DP 7C', qty_total: 10, created_at: '2026-07-28T18:00:00Z', uploaded_at: null },
  { username: 'sari', rack: 'Rak 1', product_name: 'Mentega Simas', qty_total: 5, created_at: '2026-07-28T10:00:00Z', uploaded_at: '2026-07-28T11:00:00Z' },
  { username: 'budi', rack: 'Rak 2', product_name: 'Tepung Segitiga', qty_total: 3, created_at: '2026-07-28T09:00:00Z', uploaded_at: null },
]
// "sekarang" = 2026-07-29 08:00 WIB
const now = new Date('2026-07-29T01:00:00Z')

describe('rackProgress', () => {
  it('hitung open/uploaded per rak, rak kosong ikut', () => {
    const p = rackProgress(entries, ['Rak 1', 'Rak 2', 'Rak 3'])
    expect(p).toHaveLength(3)
    expect(p[0]).toEqual({ rack: 'Rak 1', open: 1, uploaded: 1, lastAt: '2026-07-28T18:00:00Z' })
    expect(p[1].open).toBe(1)
    expect(p[2]).toEqual({ rack: 'Rak 3', open: 0, uploaded: 0, lastAt: null })
  })
})

describe('staffActivity', () => {
  it('today pakai tanggal WIB, urut lastAt desc', () => {
    const a = staffActivity(entries, now)
    expect(a[0]).toEqual({ username: 'sari', today: 1, total: 2, lastAt: '2026-07-28T18:00:00Z' })
    expect(a[1].username).toBe('budi')
    expect(a[1].today).toBe(0)
  })
})

describe('latestEntries', () => {
  it('urut created_at desc, maks n', () => {
    const l = latestEntries(entries, 2)
    expect(l).toHaveLength(2)
    expect(l[0].product_name).toBe('Mika DP 7C')
  })
})
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `npm test`
Expected: FAIL — `Failed to resolve import "./adminStats"`.

- [ ] **Step 3: Implementasi minimal**

Buat `src/lib/adminStats.js`:

```js
// Rekap entri untuk dashboard admin. Semua fungsi murni.
const wibDate = (d) => new Date(d).toLocaleDateString('sv-SE', { timeZone: 'Asia/Jakarta' })

export function rackProgress(entries, rackNames) {
  const byRack = new Map(rackNames.map((r) => [r, { rack: r, open: 0, uploaded: 0, lastAt: null }]))
  for (const e of entries) {
    const row = byRack.get(e.rack)
    if (!row) continue
    if (e.uploaded_at) row.uploaded++
    else row.open++
    if (!row.lastAt || e.created_at > row.lastAt) row.lastAt = e.created_at
  }
  return [...byRack.values()]
}

export function staffActivity(entries, now = new Date()) {
  const today = wibDate(now)
  const byUser = new Map()
  for (const e of entries) {
    let row = byUser.get(e.username)
    if (!row) byUser.set(e.username, (row = { username: e.username, today: 0, total: 0, lastAt: null }))
    row.total++
    if (wibDate(e.created_at) === today) row.today++
    if (!row.lastAt || e.created_at > row.lastAt) row.lastAt = e.created_at
  }
  return [...byUser.values()].sort((a, b) => (b.lastAt || '').localeCompare(a.lastAt || ''))
}

export function latestEntries(entries, n = 20) {
  return [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, n)
}
```

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `npm test`
Expected: PASS semua (termasuk test lama).

- [ ] **Step 5: Commit**

```bash
git add src/lib/adminStats.js src/lib/adminStats.test.js
git commit -m "feat: helper rekap dashboard admin (rak, karyawan, entri terbaru)"
```

---

### Task 2: Edge Function `admin-create-user`

**Files:**
- Create: `supabase/functions/admin-create-user/index.ts`

**Interfaces:**
- Consumes: header `Authorization: Bearer <JWT user>` (dikirim otomatis oleh `supabase.functions.invoke`).
- Produces (dipakai Task 3):
  - Body `{action: 'list'}` → 200 `{ok: true, users: [{email, created_at}]}`.
  - Body `{action: 'create', username, password}` → 200 `{ok: true, username}` atau 200 `{ok: false, error}` (error app-level: username invalid/dipakai, password pendek).
  - Bukan admin → 403; tanpa login → 401.

- [ ] **Step 1: Tulis function**

Buat `supabase/functions/admin-create-user/index.ts`:

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
    if (user.email !== 'admin@tokokartini.app') return json({ ok: false, error: 'Forbidden' }, 403)

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
    const { action, username, password } = await req.json()

    if (action === 'list') {
      const { data, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 100 })
      if (error) return json({ ok: false, error: error.message })
      const users = data.users
        .map((u) => ({ email: u.email ?? '', created_at: u.created_at }))
        .sort((a, b) => a.email.localeCompare(b.email))
      return json({ ok: true, users })
    }

    if (action === 'create') {
      const uname = String(username ?? '').trim().toLowerCase()
      if (!/^[a-z0-9._-]{2,30}$/.test(uname))
        return json({ ok: false, error: 'Username 2-30 karakter: huruf kecil, angka, titik, strip' })
      if (String(password ?? '').length < 8)
        return json({ ok: false, error: 'Password minimal 8 karakter' })
      const email = `${uname}@tokokartini.app`
      const { error } = await admin.auth.admin.createUser({ email, password, email_confirm: true })
      if (error) {
        const dup = /already|registered|exists/i.test(error.message)
        return json({ ok: false, error: dup ? 'Username sudah dipakai' : error.message })
      }
      return json({ ok: true, username: uname })
    }

    return json({ ok: false, error: 'Action tidak dikenal' })
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500)
  }
})
```

- [ ] **Step 2: Cek tidak ada salah ketik nyata**

Belum bisa dites tanpa deploy (deploy = Task 4, butuh token dari Sopian). Verifikasi manual: baca ulang file, pastikan pola auth identik `upload-rak/index.ts:45-54`, dan tiap cabang `action` selalu `return`.

- [ ] **Step 3: Commit**

```bash
git add supabase/functions/admin-create-user/index.ts
git commit -m "feat: edge function admin-create-user (bikin akun + daftar akun, hanya admin)"
```

---

### Task 3: Halaman `Admin.jsx` + cabang di `App.jsx`

**Files:**
- Create: `src/pages/Admin.jsx`
- Modify: `src/App.jsx:24-28`

**Interfaces:**
- Consumes: `rackProgress`, `staffActivity`, `latestEntries` dari `src/lib/adminStats.js` (Task 1); Edge Function `admin-create-user` (Task 2); `supabase` dari `src/lib/supabase.js`.
- Produces: komponen `Admin({ username })` (default export).

- [ ] **Step 1: Tulis `src/pages/Admin.jsx`**

```jsx
import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { rackProgress, staffActivity, latestEntries } from '../lib/adminStats'

const jam = (iso) =>
  iso
    ? new Date(iso).toLocaleString('id-ID', {
        timeZone: 'Asia/Jakarta', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    : '—'

async function fetchAllEntries() {
  const all = []
  for (let page = 0; page < 10; page++) {
    const { data, error } = await supabase
      .from('count_entries')
      .select('username, rack, product_name, qty_total, created_at, uploaded_at')
      .order('created_at', { ascending: false })
      .range(page * 1000, page * 1000 + 999)
    if (error) throw error
    all.push(...data)
    if (data.length < 1000) break
  }
  return all
}

export default function Admin({ username }) {
  const [entries, setEntries] = useState(null)
  const [racks, setRacks] = useState([])
  const [loadErr, setLoadErr] = useState(false)

  const [accounts, setAccounts] = useState([])
  const [newUser, setNewUser] = useState('')
  const [newPass, setNewPass] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  async function load() {
    setLoadErr(false)
    setEntries(null)
    try {
      const [ents, rk] = await Promise.all([
        fetchAllEntries(),
        supabase.from('racks').select('name').eq('active', true).order('sort'),
      ])
      if (rk.error) throw rk.error
      setEntries(ents)
      setRacks((rk.data || []).map((r) => r.name))
    } catch {
      setLoadErr(true)
    }
  }

  async function loadAccounts() {
    const { data, error } = await supabase.functions.invoke('admin-create-user', { body: { action: 'list' } })
    if (!error && data?.ok) setAccounts(data.users)
  }

  useEffect(() => { load(); loadAccounts() }, [])

  async function createAccount(e) {
    e.preventDefault()
    if (newPass.length < 8) { setMsg('err:Password minimal 8 karakter'); return }
    setBusy(true)
    setMsg('')
    const { data, error } = await supabase.functions.invoke('admin-create-user', {
      body: { action: 'create', username: newUser, password: newPass },
    })
    if (error || !data?.ok) setMsg(`err:${data?.error || 'Gagal membuat akun — coba lagi'}`)
    else {
      setMsg(`ok:Akun ${data.username} jadi — login pakai username '${data.username}'`)
      setNewUser(''); setNewPass('')
      loadAccounts()
    }
    setBusy(false)
  }

  return (
    <>
      <div className="card">
        <div className="row">
          <p>Halo, {username}! Dashboard SO 📊</p>
          <button className="secondary" onClick={() => supabase.auth.signOut()}>Keluar</button>
        </div>
        <button className="secondary" onClick={load}>Muat ulang</button>
      </div>

      {loadErr && (
        <div className="card">
          <p className="error">Gagal memuat data — coba lagi</p>
          <button className="secondary" onClick={load}>Ulangi</button>
        </div>
      )}
      {!loadErr && entries === null && <p className="center">Memuat…</p>}

      {entries !== null && (
        <>
          <div className="card">
            <h2>Progress rak</h2>
            {rackProgress(entries, racks).map((r) => (
              <div className="row" key={r.rack}>
                <span>{r.rack}</span>
                <span className="muted">
                  {r.open + r.uploaded === 0
                    ? 'belum dihitung'
                    : `${r.open} terbuka · ${r.uploaded} terupload · terakhir ${jam(r.lastAt)}`}
                </span>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>Aktivitas karyawan</h2>
            {staffActivity(entries).length === 0 && <p className="muted">Belum ada entri</p>}
            {staffActivity(entries).map((a) => (
              <div className="row" key={a.username}>
                <span>{a.username}</span>
                <span className="muted">{a.today} hari ini · {a.total} total · terakhir {jam(a.lastAt)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>Entri terbaru</h2>
            {latestEntries(entries).map((e, i) => (
              <div className="row" key={i}>
                <span>{e.product_name}</span>
                <span className="muted">{e.qty_total} · {e.rack} · {e.username} · {jam(e.created_at)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="card">
        <h2>Kelola akun</h2>
        <form onSubmit={createAccount}>
          <label>Username</label>
          <input value={newUser} onChange={(e) => setNewUser(e.target.value)} required />
          <label>Password (min 8 karakter)</label>
          <input type="text" value={newPass} onChange={(e) => setNewPass(e.target.value)} required />
          <button className="primary" disabled={busy || !newUser || !newPass}>
            {busy ? 'Membuat…' : 'Buat akun'}
          </button>
        </form>
        {msg && (
          <p className={msg.startsWith('ok:') ? 'ok' : 'error'}>{msg.slice(msg.indexOf(':') + 1)}</p>
        )}
        <h2>Akun terdaftar</h2>
        {accounts.map((u) => (
          <div className="row" key={u.email}>
            <span>{u.email.split('@')[0]}</span>
            <span className="muted">dibuat {u.created_at?.slice(0, 10)}</span>
          </div>
        ))}
      </div>
    </>
  )
}
```

Catatan: password sengaja `type="text"` supaya admin bisa lihat dan salin ke karyawan.

- [ ] **Step 2: Cabang admin di `App.jsx`**

Ubah `src/App.jsx` — tambah import dan cabang (baris 19-28 sekarang):

```jsx
import Admin from './pages/Admin'
// ...
const username = session?.user?.email?.split('@')[0] || ''
const isAdmin = username === 'admin'

return (
  <>
    <h1>📦 Stok Opname Kartini <span className="sub">Toko Kartini</span></h1>
    {!session && <Login />}
    {session && isAdmin && <Admin username={username} />}
    {session && !isAdmin && !rack && <Home username={username} onStart={setRack} />}
    {session && !isAdmin && rack && (
      <Count session={session} username={username} rack={rack} onChangeRack={() => setRack(null)} />
    )}
  </>
)
```

- [ ] **Step 3: Jalankan test lama + build**

Run: `npm test` → Expected: PASS (tidak ada test baru di task ini; helper sudah dites Task 1).
Run: `npm run build` → Expected: sukses tanpa error.

- [ ] **Step 4: Tes manual di dev server**

Run: `npm run dev` → buka localhost, login `admin` (password ada di catatan pribadi Sopian, jangan ditulis di repo) → dashboard tampil (kartu "Kelola akun" mungkin gagal list karena function belum dideploy — itu diharapkan sampai Task 4). Logout → login akun karyawan uji → alur SO normal.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Admin.jsx src/App.jsx
git commit -m "feat: halaman admin — dashboard SO + kelola akun"
```

---

### Task 4: Deploy + smoke test ujung-ke-ujung

**Files:**
- Modify: — (deploy saja)

**Interfaces:**
- Consumes: Edge Function Task 2, frontend Task 3.
- Produces: fitur live di https://tokokartini.github.io.

- [ ] **Step 1: Minta token deploy ke Sopian**

Deploy Edge Function butuh `SUPABASE_ACCESS_TOKEN` (token lama sudah dihapus). Minta Sopian buat di https://supabase.com/dashboard/account/tokens lalu berikan. JANGAN commit token.

- [ ] **Step 2: Deploy Edge Function**

```powershell
cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"
$env:SUPABASE_ACCESS_TOKEN = "<token dari Sopian>"
npx supabase functions deploy admin-create-user --project-ref qfqulgkpbjceizrapyom --use-api
```

Expected: deploy sukses, function tampil di Dashboard → Edge Functions.

- [ ] **Step 3: Push frontend**

```bash
git push origin main
```

Expected: GitHub Actions hijau, https://tokokartini.github.io terupdate (±2 menit).

- [ ] **Step 4: Smoke test live**

1. Login `admin` → dashboard tampil, daftar akun terisi (admin, tes).
2. Buat akun percobaan `coba` / `CobaSO2026!` → pesan sukses, muncul di daftar.
3. Logout → login `coba` → masuk alur SO (Home), BUKAN dashboard.
4. Login `tes` → alur SO normal.
5. (Opsional) Hapus akun `coba` via `python scripts/create_user.py --list` + Supabase Dashboard.

- [ ] **Step 5: Selesai**

Laporkan hasil smoke test ke Sopian. Tidak ada commit di task ini kecuali ada perbaikan bug.
