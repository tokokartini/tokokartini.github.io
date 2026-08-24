import { useState } from 'react'
import { MODES, MODE_KEYS } from '../lib/mutasi'
import { useRacks } from '../lib/racks'

// Halaman depan: pilih pekerjaan dulu, baru lokasinya.
//
// Sebelumnya halaman ini langsung menyodorkan daftar rak, karena stock opname
// satu-satunya pekerjaan. Sekarang ada tiga alur mutasi juga, dan isi ulang
// display adalah yang dikerjakan tiap hari -- jadi dia yang paling menonjol,
// sementara SO turun ke kelompok bulanan.
export default function Home({ onStart, onKeluar }) {
  const racks = useRacks()
  const [rack, setRack] = useState(localStorage.getItem('so-rack') || '')
  const [pilihRak, setPilihRak] = useState(false)
  const terpilih = racks.includes(rack) ? rack : (racks[0] || '')

  if (pilihRak) {
    return (
      <div className="card">
        <p className="section-title">Rak yang dihitung</p>
        {!racks.length && <p className="muted">Memuat daftar rak… (butuh sinyal sekali di awal)</p>}
        <div className="rack-list">
          {racks.map((r) => (
            <button
              type="button"
              key={r}
              className={`rack-opt${r === terpilih ? ' on' : ''}`}
              aria-pressed={r === terpilih}
              onClick={() => setRack(r)}
            >
              <span className="dot" aria-hidden="true" />
              {r}
            </button>
          ))}
        </div>
        <button
          className="primary"
          disabled={!terpilih}
          onClick={() => { localStorage.setItem('so-rack', terpilih); onStart(terpilih) }}
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
