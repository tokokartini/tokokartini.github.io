import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'
import { MODES, MODE_KEYS } from '../lib/mutasi'

// Halaman depan: pilih pekerjaan dulu, baru lokasinya.
//
// Sebelumnya halaman ini langsung menyodorkan daftar rak, karena stock opname
// satu-satunya pekerjaan. Sekarang ada tiga alur mutasi juga, dan isi ulang
// display adalah yang dikerjakan tiap hari -- jadi dia yang paling menonjol,
// sementara SO turun ke kelompok bulanan.
export default function Home({ onStart, onKeluar }) {
  const [racks, setRacks] = useState([])
  const [rack, setRack] = useState(localStorage.getItem('so-rack') || '')
  const [pilihRak, setPilihRak] = useState(false)

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

  if (pilihRak) {
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
        <button
          className="primary"
          disabled={!rack}
          onClick={() => { localStorage.setItem('so-rack', rack); onStart(rack) }}
        >
          Mulai Hitung →
        </button>
        <button className="secondary" style={{ marginTop: 10, width: '100%' }} onClick={() => setPilihRak(false)}>
          Kembali
        </button>
      </div>
    )
  }

  return (
    <div className="card">
      <p className="section-title">Pekerjaan hari ini</p>
      <MenuOpt modeKey="display" utama onKlik={onKeluar} />

      <p className="menu-sep">Lebih jarang</p>
      {MODE_KEYS.filter((k) => k !== 'display').map((k) => (
        <MenuOpt key={k} modeKey={k} onKlik={onKeluar} />
      ))}

      <p className="menu-sep">Bulanan</p>
      <button className="menu-opt" onClick={() => setPilihRak(true)}>
        <span className="ico" aria-hidden="true">📋</span>
        <span>
          <span className="t">Hitung Stok</span>
          <span className="s">Stock opname per gudang</span>
        </span>
        <span className="arw" aria-hidden="true">›</span>
      </button>
    </div>
  )
}

function MenuOpt({ modeKey, utama, onKlik }) {
  const m = MODES[modeKey]
  return (
    <button className={`menu-opt${utama ? ' utama' : ''}`} onClick={() => onKlik(modeKey)}>
      <span className="ico" aria-hidden="true">{m.ico}</span>
      <span>
        <span className="t">{m.judul}</span>
        <span className="s">{m.sub}</span>
      </span>
      <span className="arw" aria-hidden="true">›</span>
    </button>
  )
}
