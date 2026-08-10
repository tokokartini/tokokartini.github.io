import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { rackProgress, staffActivity, latestEntries } from '../lib/adminStats'

const jam = (iso) =>
  iso
    ? new Date(iso).toLocaleString('id-ID', {
        timeZone: 'Asia/Jakarta', year: 'numeric', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
      })
    : '—'

// Job malam jam 03:00 WIB gagal secara diam-diam kalau seluruh sync_runs kosong
// atau baris terbarunya sudah lama -- 36 jam kasih jeda lebih dari 24 jam supaya
// satu malam yang telat/gagal-lalu-berhasil-manual besoknya tidak langsung merah,
// tapi dua malam berturut-turut gagal pasti kelewat 36 jam.
const SYNC_STALE_MS = 36 * 3600e3
const syncStale = (s) => !s || Date.now() - new Date(s.ran_at).getTime() > SYNC_STALE_MS

async function fetchAllEntries() {
  const all = []
  const since = new Date(Date.now() - 30 * 86400e3).toISOString()
  for (let page = 0; page < 10; page++) {
    const { data, error } = await supabase
      .from('count_entries')
      .select('username, rack, product_name, qty_total, created_at, updated_at, uploaded_at')
      // Entri terbuka lama (belum di-upload) tidak boleh hilang dari dashboard cuma karena
      // umurnya lewat 30 hari — kalau begitu, "siapa yang belum upload" jadi tidak terjawab.
      .or(`created_at.gte.${since},uploaded_at.is.null`)
      .order('created_at', { ascending: false })
      .range(page * 1000, page * 1000 + 999)
    if (error) throw error
    all.push(...data)
    if (data.length < 1000) break
  }
  return all
}

export default function Admin() {
  const [entries, setEntries] = useState(null)
  const [racks, setRacks] = useState([])
  const [loadErr, setLoadErr] = useState(false)

  const [accounts, setAccounts] = useState([])
  const [acctErr, setAcctErr] = useState(false)
  const [acctBusy, setAcctBusy] = useState('')
  const [newUser, setNewUser] = useState('')
  const [newPass, setNewPass] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const [sync, setSync] = useState(null)
  const [syncErr, setSyncErr] = useState(false)
  const [syncBusy, setSyncBusy] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')

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
    if (error || !data?.ok) { setAcctErr(true); setAccounts([]) }
    else { setAcctErr(false); setAccounts(data.users) }
  }

  async function loadSync() {
    setSyncErr(false)
    try {
      const { data, error } = await supabase
        .from('sync_runs').select('*').order('ran_at', { ascending: false }).limit(1)
      if (error) throw error
      setSync(data?.[0] ?? null)
    } catch {
      setSyncErr(true)
    }
  }

  useEffect(() => { load(); loadAccounts(); loadSync() }, [])

  const racksView = useMemo(() => (entries ? rackProgress(entries, racks) : []), [entries, racks])
  const staff = useMemo(() => (entries ? staffActivity(entries) : []), [entries])
  const latest = useMemo(() => (entries ? latestEntries(entries) : []), [entries])
  const total = useMemo(
    () => ({
      hariIni: staff.reduce((n, a) => n + a.today, 0),
      terbuka: staff.reduce((n, a) => n + a.open, 0),
    }),
    [staff],
  )

  async function createAccount(e) {
    e.preventDefault()
    if (newPass.length < 8) { setMsg('err:Password minimal 8 karakter'); return }
    setBusy(true)
    setMsg('')
    try {
      const { data, error } = await supabase.functions.invoke('admin-create-user', {
        body: { action: 'create', username: newUser, password: newPass },
      })
      if (error || !data?.ok) setMsg(`err:${data?.error || 'Gagal membuat akun — coba lagi'}`)
      else {
        setMsg(`ok:Akun ${data.username} jadi — login pakai username '${data.username}'`)
        setNewUser(''); setNewPass('')
        loadAccounts()
      }
    } finally {
      setBusy(false)
    }
  }

  async function ubahAkun(uname, email, action) {
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
    try {
      const { data, error } = await supabase.functions.invoke('admin-create-user', {
        body: { action, email },
      })
      if (error || !data?.ok) setMsg(`err:${data?.error || 'Gagal mengubah akun — coba lagi'}`)
      else if (data.mode === 'deleted') setMsg(`ok:Akun ${uname} dihapus permanen (belum pernah input SO)`)
      else if (data.mode === 'banned') setMsg(`ok:Akun ${uname} dinonaktifkan — ${data.entries} entri SO tetap tersimpan`)
      else setMsg(`ok:Akun ${uname} diaktifkan lagi`)
      await loadAccounts()
    } finally {
      setAcctBusy('')
    }
  }

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

  return (
    <>
      {entries !== null && (
        <div className="stats">
          <div className="stat">
            <div className="n">{total.hariIni}</div>
            <div className="l">hari ini</div>
          </div>
          <div className="stat">
            <div className="n" style={{ color: 'var(--orange)' }}>{total.terbuka}</div>
            <div className="l">belum upload</div>
          </div>
          <div className="stat">
            <div className="n">{staff.length}</div>
            <div className="l">karyawan</div>
          </div>
        </div>
      )}

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
            <p className="section-title">
              <span>Progress rak · 30 hari</span>
              <span className="spacer" />
              <button className="secondary" onClick={load}>Muat ulang</button>
            </p>
            {racksView.map((r) => {
              const jml = r.open + r.uploaded
              // Bar dua warna: hijau = sudah terupload, oranye = masih terbuka.
              const pUp = jml ? (r.uploaded / jml) * 100 : 0
              const pOpen = jml ? (r.open / jml) * 100 : 0
              return (
                <div className="rack-stat" key={r.rack}>
                  <div className="top">
                    <span className="nm">{r.rack}</span>
                    <span className="muted">{jml === 0 ? 'belum dihitung' : `${jml} entri`}</span>
                  </div>
                  {jml > 0 && (
                    <>
                      <div className="bar">
                        <i className="up" style={{ width: `${pUp}%` }} />
                        <i className="open" style={{ width: `${pOpen}%` }} />
                      </div>
                      <span className="muted">
                        {r.uploaded} terupload · {r.open} terbuka · terakhir {jam(r.lastAt)}
                      </span>
                    </>
                  )}
                </div>
              )
            })}
          </div>

          <div className="card">
            <p className="section-title">Aktivitas karyawan</p>
            {staff.length === 0 && <p className="muted">Belum ada entri</p>}
            {staff.map((a) => (
              <div className="data-row" key={a.username}>
                <span className="k">{a.username}</span>
                {a.open > 0 && <span className="badge soft">{a.open} belum upload</span>}
                <span className="v">{a.today} hari ini · {a.total} total · {jam(a.lastAt)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <p className="section-title">Entri terbaru</p>
            {latest.map((e, i) => (
              <div className="data-row" key={i}>
                <span className="k">{e.product_name}</span>
                <span className="v">{e.qty_total} · {e.rack} · {e.username} · {jam(e.created_at)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="card">
        <p className="section-title">Produk</p>
        {syncErr &&<p className="error">Gagal memuat riwayat sync — coba muat ulang halaman</p>}
        {!syncErr && (
          <p className={syncStale(sync) ? 'error' : 'muted'} style={{ marginBottom: 12 }}>
            {sync
              ? `terakhir sync: ${jam(sync.ran_at)} (${sync.source}) · ${
                  sync.ok
                    ? `${sync.total} produk, ${sync.added} baru, ${sync.deactivated} dinonaktifkan`
                    : `GAGAL — ${sync.error}`
                }`
              : 'belum pernah sync'}
            {syncStale(sync) ? ' — cek job malam' : ''}
          </p>
        )}
        {syncMsg && (
          <p className={syncMsg.startsWith('ok:') ? 'ok' : 'error'}>{syncMsg.slice(syncMsg.indexOf(':') + 1)}</p>
        )}
        <button className="secondary" disabled={syncBusy} onClick={syncProduk}>
          {syncBusy ? 'Menarik data…' : '🔄 Sync produk'}
        </button>
      </div>

      <div className="card">
        <p className="section-title">Kelola akun</p>
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
        <p className="section-title" style={{ marginTop: 22 }}>Akun terdaftar</p>
        {acctErr && <p className="error">Gagal memuat daftar akun — coba muat ulang halaman</p>}
        {!acctErr && accounts.length === 0 && <p className="muted">Belum ada akun</p>}
        {accounts.map((u) => {
          const uname = u.email.split('@')[0]
          const barisAdmin = u.email === 'admin@tokokartini.app'
          return (
            <div className="data-row" key={u.email}>
              <span className="k">
                {uname}
                {u.banned && <span className="muted"> · nonaktif</span>}
              </span>
              {barisAdmin ? (
                <span className="muted">akun admin</span>
              ) : (
                <button
                  className="secondary"
                  disabled={!!acctBusy}
                  onClick={() => ubahAkun(uname, u.email, u.banned ? 'reactivate' : 'deactivate')}
                >
                  {acctBusy === uname ? '…' : u.banned ? 'Aktifkan' : 'Hapus'}
                </button>
              )}
            </div>
          )
        })}
      </div>
    </>
  )
}
