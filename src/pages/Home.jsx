import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Home({ username, onStart }) {
  const [racks, setRacks] = useState([])
  const [rack, setRack] = useState(localStorage.getItem('so-rack') || '')

  useEffect(() => {
    supabase
      .from('racks')
      .select('name')
      .eq('active', true)
      .order('sort')
      .then(({ data }) => {
        const names = (data || []).map((r) => r.name)
        setRacks(names)
        if (names.length && !names.includes(rack)) setRack(names[0])
      })
  }, [])

  return (
    <div className="card">
      <div className="row">
        <p>Halo, {username}! Semangat ya 🔥</p>
        <button className="secondary" onClick={() => supabase.auth.signOut()}>Keluar</button>
      </div>
      <label>Rak yang dihitung</label>
      <select value={rack} onChange={(e) => setRack(e.target.value)}>
        {racks.map((r) => <option key={r}>{r}</option>)}
      </select>
      <button className="primary" disabled={!rack} onClick={() => { localStorage.setItem('so-rack', rack); onStart(rack) }}>
        Mulai Hitung
      </button>
    </div>
  )
}
