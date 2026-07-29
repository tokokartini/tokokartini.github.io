import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Login from './pages/Login'
import Home from './pages/Home'
import Count from './pages/Count'
import Admin from './pages/Admin'

export default function App() {
  const [session, setSession] = useState(undefined)
  const [rack, setRack] = useState(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  if (session === undefined) return <p className="center">Memuat…</p>

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
}
