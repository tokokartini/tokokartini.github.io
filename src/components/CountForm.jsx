import { useState } from 'react'
import { totalQty } from '../lib/convert'

export default function CountForm({ group, initial, onSave, onCancel }) {
  const [units, setUnits] = useState(
    group.units.map((u) => {
      const prev = initial?.units?.find((x) => x.sku === u.sku)
      return { ...u, qty: prev?.qty ?? '' }
    }),
  )
  const [expired, setExpired] = useState(initial?.expired_date || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function setQty(sku, qty) {
    setUnits((us) => us.map((u) => (u.sku === sku ? { ...u, qty } : u)))
  }

  async function save() {
    setBusy(true)
    setError('')
    try {
      await onSave(units.map(({ sku, variant, mult, qty }) => ({ sku, variant, mult, qty: Number(qty) || 0 })), expired)
    } catch (e) {
      setError(e.message)
    }
    setBusy(false)
  }

  return (
    <div className="card">
      <h3>{group.name}</h3>
      {units.map((u) => (
        <div className="unit-row" key={u.sku}>
          <label>{u.variant} <span className="muted">×{u.mult}</span></label>
          <input type="number" inputMode="numeric" min="0" value={u.qty} onChange={(e) => setQty(u.sku, e.target.value)} />
        </div>
      ))}
      <label>Tanggal ED (opsional)</label>
      <input type="date" value={expired} onChange={(e) => setExpired(e.target.value)} />
      <p className="total">{totalQty(units)}</p>
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button className="primary" disabled={busy} onClick={save}>{busy ? 'Menyimpan…' : 'Simpan'}</button>
        <button className="secondary" disabled={busy} onClick={onCancel}>Batal</button>
      </div>
    </div>
  )
}
