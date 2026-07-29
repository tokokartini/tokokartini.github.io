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
