import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Home({ onStart }) {
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
      <p className="section-title">Rak yang dihitung</p>
      {!racks.length && <p className="muted">Memuat daftar rak…</p>}
      <div className="rack-list">
        {racks.map((r) => (
          <button
            type="button"
            key={r}
            className={`rack-opt${r === rack ? ' on' : ''}`}
            aria-pressed={r === rack}
            onClick={() => setRack(r)}
          >
            <span className="dot" aria-hidden="true" />
            {r}
          </button>
        ))}
      </div>
      <button className="primary" disabled={!rack} onClick={() => { localStorage.setItem('so-rack', rack); onStart(rack) }}>
        Mulai Hitung →
      </button>
    </div>
  )
}
