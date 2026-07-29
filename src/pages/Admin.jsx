import { useEffect, useMemo, useState } from 'react'
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
  const since = new Date(Date.now() - 30 * 86400e3).toISOString()
  for (let page = 0; page < 10; page++) {
    const { data, error } = await supabase
      .from('count_entries')
      .select('username, rack, product_name, qty_total, created_at, updated_at, uploaded_at')
      .gte('created_at', since)
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
  const [acctErr, setAcctErr] = useState(false)
  const [acctBusy, setAcctBusy] = useState('')
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
    if (error || !data?.ok) { setAcctErr(true); setAccounts([]) }
    else { setAcctErr(false); setAccounts(data.users) }
  }

  useEffect(() => { load(); loadAccounts() }, [])

  const racksView = useMemo(() => (entries ? rackProgress(entries, racks) : []), [entries, racks])
  const staff = useMemo(() => (entries ? staffActivity(entries) : []), [entries])
  const latest = useMemo(() => (entries ? latestEntries(entries) : []), [entries])

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
            <h2>Progress rak <span className="muted">(30 hari terakhir)</span></h2>
            {racksView.map((r) => (
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
            {staff.length === 0 && <p className="muted">Belum ada entri</p>}
            {staff.map((a) => (
              <div className="row" key={a.username}>
                <span>{a.username}</span>
                <span className="muted">{a.today} hari ini · {a.total} total · terakhir {jam(a.lastAt)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>Entri terbaru</h2>
            {latest.map((e, i) => (
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
