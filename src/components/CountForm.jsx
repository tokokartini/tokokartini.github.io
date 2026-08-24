import { useEffect, useRef, useState } from 'react'
import { totalQty } from '../lib/convert'

// `showExpired` dimatikan halaman Pengeluaran: tanggal ED milik stock opname, tidak
// ada artinya untuk barang yang cuma pindah rak. Lembar isian jumlahnya sendiri
// dipakai bersama supaya kedua halaman tidak pernah punya aturan satuan berbeda.
export default function CountForm({ group, initial, colleagueHint, subtitle, showExpired = true, saveLabel = 'Simpan', onSave, onCancel }) {
  const [units, setUnits] = useState(
    group.units.map((u) => {
      const prev = initial?.units?.find((x) => x.sku === u.sku)
      return { ...u, qty: prev?.qty ?? '' }
    }),
  )
  const [expired, setExpired] = useState(initial?.expired_date || '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const kolomPertama = useRef(null)

  // Fokus ke kolom jumlah pertama begitu lembar naik. Tanpa ini karyawan harus
  // mengetuk kolomnya dulu -- satu ketukan ekstra dikali ratusan produk per SO.
  //
  // `preventScroll` supaya papan ketik naik tanpa lembar ikut melompat, dan diberi
  // jeda satu frame supaya animasi naiknya tidak terpotong.
  useEffect(() => {
    const t = setTimeout(() => kolomPertama.current?.focus({ preventScroll: true }), 120)
    return () => clearTimeout(t)
  }, [])

  // Esc menutup lembar.
  //
  // Tombol Back Android SENGAJA tidak ikut ditangani. Caranya harus `pushState` saat
  // lembar naik lalu `history.back()` saat ditutup dari tombol Simpan/Batal, dan
  // `back()` itu asinkron: kalau lembar berikutnya dibuka sebelum pop-nya mendarat,
  // pop yang tertunda memakan entri lembar baru dan Back berikutnya MELEMPAR
  // karyawan keluar dari halaman hitung. Terukur di uji Chrome. Back yang merusak
  // lebih buruk daripada Back yang tidak melakukan apa-apa.
  useEffect(() => {
    const esc = (e) => { if (e.key === 'Escape' && !busy) onCancel() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [busy, onCancel])

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

  // Lembar naik dari bawah layar, bukan kartu di tengah daftar: satu produk =
  // satu layar penuh, jempol tetap di dekat tombol Simpan.
  return (
    <div
      className="sheet-wrap"
      role="dialog"
      aria-modal="true"
      aria-label={group.name}
      onClick={(e) => { if (e.target === e.currentTarget && !busy) onCancel() }}
    >
      <div className="sheet">
        <div className="sheet-grip" aria-hidden="true" />
        <h3>{group.name}</h3>
        {subtitle && <p className="muted" style={{ marginTop: -6 }}>{subtitle}</p>}
        {colleagueHint && <p className="muted" style={{ marginTop: -6 }}>{colleagueHint}</p>}
        <div style={{ marginTop: 14 }}>
          {units.map((u, i) => (
            <div className="unit-row" key={u.sku}>
              <label>{u.variant} <span className="muted">×{u.mult}</span></label>
              <input
                ref={i === 0 ? kolomPertama : null}
                type="number"
                inputMode="numeric"
                min="0"
                value={u.qty}
                onChange={(e) => setQty(u.sku, e.target.value)}
              />
            </div>
          ))}
        </div>
        <div className="total-box">
          <span className="lbl">Total</span>
          <p className="total">{totalQty(units)}</p>
        </div>
        {showExpired && (
          <>
            <label>Tanggal ED (opsional)</label>
            <input type="date" value={expired} onChange={(e) => setExpired(e.target.value)} />
          </>
        )}
        {error && <p className="error">{error}</p>}
        <div className="actions">
          {/* Urutan Simpan-lalu-Batal dipertahankan dari versi lama — jangan ditukar,
              karyawan sudah hafal posisi jempolnya. */}
          <button className="primary" disabled={busy} onClick={save}>{busy ? 'Menyimpan…' : saveLabel}</button>
          <button className="secondary" disabled={busy} onClick={onCancel}>Batal</button>
        </div>
      </div>
    </div>
  )
}
