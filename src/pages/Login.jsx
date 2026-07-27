import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    const email = `${username.trim().toLowerCase()}@tokokartini.app`
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) setError('Username atau password salah')
    setBusy(false)
  }

  return (
    <div className="card">
      <h2>Masuk</h2>
      <form onSubmit={submit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none" required />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {error && <p className="error">{error}</p>}
        <button className="primary" disabled={busy}>{busy ? 'Masuk…' : 'Masuk'}</button>
      </form>
      <p className="muted">Belum punya akun? Minta dibuatkan admin.</p>
    </div>
  )
}
