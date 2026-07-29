# Hapus Entri di "Hasil rak ini" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Karyawan bisa membuang entri salah masuk dari kartu "Hasil rak ini" — datanya benar-benar dibuang sehingga tidak ikut ter-upload.

**Architecture:** Satu policy RLS baru (`delete` untuk entri `uploaded_at is null`) sebagai penjaga sebenarnya, lalu `useEntries` mendapat `deleteEntry(id)` dan `Count.jsx` mendapat tombol per baris. Tidak ada perubahan pada Edge Function maupun halaman admin.

**Tech Stack:** React 18 + Vite, Supabase JS v2 (RLS), PostgreSQL, Vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-hapus-entri-rak-design.md`

## Global Constraints

- Tidak ada dependency baru. Teks UI bahasa Indonesia. CSS class yang sudah ada: `card`, `row`, `entry`, `qty`, `badge`, `primary`, `secondary`, `link`, `muted`, `error`, `ok`.
- Penjaga sebenarnya adalah policy RLS, bukan tampilan: entri `uploaded_at` terisi tidak boleh bisa dihapus lewat jalur mana pun dari browser.
- Kartu "Hasil rak ini" sudah menyaring `uploaded_at` null (`src/pages/Count.jsx:29`) — jangan ubah penyaringan itu.
- Klik badan baris harus tetap membuka form edit seperti sekarang.
- Test runner `npm test` (12 lulus sekarang); build `npm run build`. Jalankan dari root `C:\Users\COMPUTER\Documents\Claude AI\so-kartini`.
- Database live: project `qfqulgkpbjceizrapyom`. `count_entries` saat ini **kosong** (data test sudah dibersihkan) — smoke test wajib mengembalikannya ke kosong.

---

### Task 1: Policy RLS untuk hapus entri terbuka

**Files:**
- Create: `supabase/migration-delete-entries.sql`
- Modify: `supabase/schema.sql`

**Interfaces:**
- Consumes: tabel `count_entries` (kolom `uploaded_at`).
- Produces (dipakai Task 2): policy `delete open entries` — `DELETE` diizinkan untuk `authenticated` hanya bila `uploaded_at is null`.

- [ ] **Step 1: Tulis file migrasi**

Buat `supabase/migration-delete-entries.sql`:

```sql
-- Izinkan karyawan membuang entri yang salah masuk (mis. produk ternyata sudah
-- dihitung di rak lain). Dibatasi ke entri yang BELUM di-upload: entri terupload
-- sudah punya baris pasangan di tab Log spreadsheet, dan menghapusnya di sini
-- akan meninggalkan baris yatim yang tidak bisa dilacak.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
create policy "delete open entries" on count_entries
  for delete to authenticated using (uploaded_at is null);
```

- [ ] **Step 2: Samakan `supabase/schema.sql`**

Di `supabase/schema.sql`, tepat setelah policy `update open entries` (baris 49-50), tambahkan policy yang sama supaya setup dari nol menghasilkan skema yang identik:

```sql
create policy "delete open entries" on count_entries
  for delete to authenticated using (uploaded_at is null);
```

- [ ] **Step 3: Verifikasi baca-ulang**

Tidak ada yang bisa dijalankan di task ini — penerapan ke database live dilakukan di Task 3 oleh controller. Verifikasi manual: (a) kedua file memuat policy yang sama persis; (b) nama policy `delete open entries` belum dipakai di `schema.sql`; (c) syarat `uploaded_at is null` ada di klausa `using`, bukan `with check` (`with check` tidak berlaku untuk `DELETE`).

- [ ] **Step 4: Commit**

```bash
git add supabase/migration-delete-entries.sql supabase/schema.sql
git commit -m "feat: policy hapus entri yang belum di-upload"
```

---

### Task 2: Tombol hapus di "Hasil rak ini"

**Files:**
- Modify: `src/lib/useEntries.js`
- Modify: `src/pages/Count.jsx`
- Modify: `src/styles.css`

**Interfaces:**
- Consumes: policy dari Task 1.
- Produces: `deleteEntry(id)` dari hook `useEntries` — resolve bila terhapus, `throw new Error(<pesan Indonesia>)` bila gagal atau entri terkunci.

- [ ] **Step 1: Tambah `deleteEntry` di `src/lib/useEntries.js`**

Tambahkan fungsi ini tepat setelah `saveEntry`, dan ikutkan pada objek yang di-`return` di akhir hook:

```js
  async function deleteEntry(id) {
    const { data, error } = await supabase
      .from('count_entries')
      .delete()
      .eq('id', id)
      .is('uploaded_at', null)
      .select('id')
    if (error) {
      await refresh()
      throw new Error('Gagal hapus — cek sinyal, lalu coba lagi')
    }
    if (!data || data.length === 0) {
      await refresh()
      throw new Error('Entri sudah terkunci (terupload) — tidak bisa dihapus')
    }
    await refresh()
  }
```

Baris `return` di akhir hook menjadi:

```js
  return { entries, saveEntry, deleteEntry, refresh }
```

- [ ] **Step 2: Gaya tombol di `src/styles.css`**

Tambahkan tepat setelah aturan `.entry .qty` (baris 69):

```css
.entry-act { display: flex; align-items: center; gap: 12px; }
button.hapus { background: none; color: var(--error); padding: 6px 10px; font-size: 1.15rem; line-height: 1; }
button.hapus:disabled { opacity: 0.5; }
```

- [ ] **Step 3: Tombol hapus di `src/pages/Count.jsx`**

Ambil `deleteEntry` dari hook — ganti baris 11 menjadi:

```jsx
  const { entries, saveEntry, deleteEntry, refresh } = useEntries(rack, session)
```

Tambahkan dua state di bawah `uploading` (baris 13):

```jsx
  const [hapusMsg, setHapusMsg] = useState('')
  const [hapusBusy, setHapusBusy] = useState(0)
```

Tambahkan handler tepat setelah fungsi `upload` (setelah baris 50):

```jsx
  async function hapusEntri(ev, entry) {
    ev.stopPropagation()
    if (!window.confirm(
      `Hapus "${entry.product_name}" dari ${rack}?\n\n` +
        'Hitungannya dibuang dan tidak ikut ter-upload.',
    )) return
    setHapusBusy(entry.id)
    setHapusMsg('')
    try {
      await deleteEntry(entry.id)
    } catch (err) {
      setHapusMsg(`err:${err.message}`)
    } finally {
      setHapusBusy(0)
    }
  }
```

Ganti isi kartu "Hasil rak ini" (baris 85-97) menjadi:

```jsx
      <div className="card">
        <h3>Hasil rak ini</h3>
        {hapusMsg && (
          <p className={hapusMsg.startsWith('ok:') ? 'ok' : 'error'}>{hapusMsg.slice(hapusMsg.indexOf(':') + 1)}</p>
        )}
        {!openEntries.length && <p className="muted">Belum ada.</p>}
        {openEntries.map((e) => (
          <div className="entry" key={e.id} onClick={() => openFromEntry(e)}>
            <span>{e.product_name}</span>
            <span className="entry-act">
              <span className="qty">{Number(e.qty_total)}</span>
              <button
                className="hapus"
                aria-label={`Hapus ${e.product_name}`}
                disabled={hapusBusy === e.id}
                onClick={(ev) => hapusEntri(ev, e)}
              >
                {hapusBusy === e.id ? '…' : '🗑'}
              </button>
            </span>
          </div>
        ))}
        <button className="primary" disabled={uploading || !openEntries.length} onClick={upload} style={{ marginTop: 12 }}>
          {uploading ? 'Mengirim…' : '⬆️ Upload'}
        </button>
      </div>
```

- [ ] **Step 4: Jalankan test dan build**

Run: `npm test` → Expected: 12 lulus (tidak ada test baru; `deleteEntry` menyentuh Supabase sehingga tidak diuji unit — lihat catatan testing di spec).
Run: `npm run build` → Expected: sukses tanpa error.

- [ ] **Step 5: Commit**

```bash
git add src/lib/useEntries.js src/pages/Count.jsx src/styles.css
git commit -m "feat: tombol hapus entri di Hasil rak ini"
```

---

### Task 3: Terapkan policy ke database live + smoke test + deploy

**Files:** — (operasional; kalau ada bug, perbaiki di file terkait dan commit)

**Interfaces:**
- Consumes: Task 1 (SQL), Task 2 (frontend).
- Produces: fitur live di https://tokokartini.github.io.

- [ ] **Step 1: Terapkan policy ke database live**

Dilakukan controller (butuh token Supabase). Isi `supabase/migration-delete-entries.sql` dijalankan lewat Management API atau Supabase Dashboard → SQL Editor.

Expected: policy `delete open entries` muncul pada `count_entries`. Verifikasi dengan query:

```sql
select policyname, cmd, qual from pg_policies
where tablename = 'count_entries' order by policyname;
```

Harus memuat baris `delete open entries | DELETE | (uploaded_at IS NULL)`.

- [ ] **Step 2: Smoke test RLS memakai kunci anon (bukan service key)**

Yang diuji adalah policy-nya, jadi penghapusan **wajib** lewat client anon yang login sebagai karyawan. Buat `smoke_hapus.mjs` di root proyek (file sementara, dihapus di Step 4):

```js
import { createClient } from '@supabase/supabase-js'

const URL = 'https://qfqulgkpbjceizrapyom.supabase.co'
const ANON = 'sb_publishable_HDK2-JqOPUY9lFnjZ9JZYg_GpRxOzkQ'
const SERVICE = process.env.SO_SERVICE_KEY // diisi controller saat menjalankan
const log = (ok, msg) => console.log(`${ok ? 'OK  ' : 'FAIL'} ${msg}`)

const staf = createClient(URL, ANON)
const { data: auth, error: loginErr } = await staf.auth.signInWithPassword({
  email: 'tes@tokokartini.app', password: 'TesSO2026!',
})
log(!loginErr, `login tes${loginErr ? ': ' + loginErr.message : ''}`)
const uid = auth.user.id

const baru = (nama) => ({
  user_id: uid, username: 'tes', rack: 'Rak 1', product_name: nama,
  units: [{ sku: 'UJI-1', variant: 'Pcs', mult: 1, qty: 3 }], qty_total: 3,
})

// 1. entri terbuka -> boleh dihapus
const { data: a, error: aErr } = await staf.from('count_entries').insert(baru('Uji Hapus A')).select('id')
log(!aErr && a?.length === 1, `sisip entri terbuka${aErr ? ': ' + aErr.message : ''}`)
const { data: delA } = await staf.from('count_entries').delete().eq('id', a[0].id).is('uploaded_at', null).select('id')
log(delA?.length === 1, `entri terbuka terhapus: ${delA?.length ?? 0} baris`)

// 2. entri terupload -> TIDAK boleh dihapus
const { data: b } = await staf.from('count_entries').insert(baru('Uji Hapus B')).select('id')
const admin = createClient(URL, SERVICE)
await admin.from('count_entries').update({ uploaded_at: new Date().toISOString() }).eq('id', b[0].id)
const { data: delB } = await staf.from('count_entries').delete().eq('id', b[0].id).select('id')
log(!delB || delB.length === 0, `entri terupload TIDAK terhapus: ${delB?.length ?? 0} baris (harus 0)`)

// bersihkan sisa + pastikan tabel kembali kosong
await admin.from('count_entries').delete().eq('id', b[0].id)
const { count } = await admin.from('count_entries').select('id', { count: 'exact', head: true })
log(count === 0, `count_entries kembali kosong: ${count}`)

process.exit(0)
```

Run: `cd "C:\Users\COMPUTER\Documents\Claude AI\so-kartini"; $env:SO_SERVICE_KEY = "<service_role_key dari scripts/config.local.json>"; node smoke_hapus.mjs`

Expected: lima baris `OK`. Bila baris "entri terupload TIDAK terhapus" gagal, **hentikan** — itu berarti policy-nya bocor; jangan lanjut ke Step 3.

- [ ] **Step 3: Push frontend**

```bash
git push origin main
```

Lalu tunggu: `gh run list --limit 1 --json status,conclusion` → Expected `conclusion: success`.

- [ ] **Step 4: Bersihkan file sementara**

```powershell
Remove-Item "C:\Users\COMPUTER\Documents\Claude AI\so-kartini\smoke_hapus.mjs"
```

Pastikan `git status --short` bersih dan `count_entries` masih kosong.

- [ ] **Step 5: Laporkan**

Laporkan hasil smoke test dan status deploy. Tidak ada commit di task ini kecuali ada perbaikan bug.

---

### Task 4: Perbarui README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Tambah keterangan**

Baca `README.md` dulu, lalu tambahkan dengan gaya yang sudah ada (Indonesia, ringkas): di kartu "Hasil rak ini" karyawan bisa menghapus entri yang **belum di-upload** (mis. produk ternyata sudah dihitung di rak lain) — datanya dibuang jadi tidak ikut ter-upload; entri yang **sudah** di-upload terkunci dan tidak bisa dihapus dari app, perbaikannya dilakukan langsung di baris tab Log.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README — hapus entri di Hasil rak ini"
```
