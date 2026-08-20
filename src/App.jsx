import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Login from './pages/Login'
import Home from './pages/Home'
import Count from './pages/Count'
import Keluar from './pages/Keluar'
import Admin from './pages/Admin'
import { MODES } from './lib/mutasi'

export default function App() {
  const [session, setSession] = useState(undefined)
  const [rack, setRack] = useState(null)
  // Halaman surat jalan yang sedang dibuka ('display' | 'datang' | 'gudang'), atau
  // null kalau petugas masih di menu. Sengaja terpisah dari `rack` supaya alur SO
  // tidak berubah sedikit pun.
  const [modeKey, setModeKey] = useState(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  if (session === undefined) return <p className="center">Memuat…</p>

  const username = session?.user?.email?.split('@')[0] || ''
  const isAdmin = username === 'admin'

  // Baris kedua app bar = konteks "aku siapa, lagi di mana". Tombol keluar pindah
  // ke sini supaya tidak diulang di tiap halaman.
  const subtitle = !session
    ? 'Toko Kartini'
    : isAdmin
      ? 'Dashboard admin'
      : modeKey
        ? `${username} · ${MODES[modeKey].judul}`
        : rack
          ? `${username} · ${rack}`
          : `Halo, ${username}! Semangat ya 🔥`

  return (
    <>
      <header className="appbar">
        <div className="appbar-in">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">📦</span>
            <div style={{ minWidth: 0 }}>
              <div className="brand-title">Stok Opname</div>
              <div className="brand-sub">{subtitle}</div>
            </div>
          </div>
          {session && (
            <button className="icon-btn" aria-label="Keluar" title="Keluar" onClick={() => supabase.auth.signOut()}>
              ⏻
            </button>
          )}
        </div>
      </header>

      <main className={`page${session && !isAdmin && (rack || modeKey) ? ' has-actionbar' : ''}`}>
        {!session && <Login />}
        {session && isAdmin && <Admin username={username} />}
        {session && !isAdmin && !rack && !modeKey && (
          <Home username={username} onStart={setRack} onKeluar={setModeKey} />
        )}
        {session && !isAdmin && modeKey && (
          <Keluar session={session} modeKey={modeKey} onSelesai={() => setModeKey(null)} />
        )}
        {session && !isAdmin && rack && !modeKey && (
          <Count session={session} username={username} rack={rack} onChangeRack={() => setRack(null)} />
        )}
      </main>
    </>
  )
}
