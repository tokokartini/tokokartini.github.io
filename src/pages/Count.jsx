import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { groupProducts, filterGroups } from '../lib/groupProducts'
import { useEntries } from '../lib/useEntries'
import CountForm from '../components/CountForm'

export default function Count({ session, username, rack, onChangeRack }) {
  const [groups, setGroups] = useState([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // { group, entry|null }
  const { entries, othersOpen, saveEntry, deleteEntry, refresh } = useEntries(rack, session)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploading, setUploading] = useState(false)
  const [hapusMsg, setHapusMsg] = useState('')
  const [hapusBusy, setHapusBusy] = useState(0)

  useEffect(() => {
    let all = []
    async function load(offset = 0) {
      const { data } = await supabase
        .from('products').select('*').eq('active', true)
        .range(offset, offset + 999)
      all = all.concat(data || [])
      if ((data || []).length === 1000) return load(offset + 1000)
      setGroups(groupProducts(all))
    }
    load()
  }, [])

  const results = useMemo(() => filterGroups(groups, query).slice(0, 20), [groups, query])
  const openEntries = entries.filter((e) => !e.uploaded_at)

  // Peringatan read-only: rekan lain sudah punya entri terbuka untuk produk ini di rak
  // ini. Cuma tampilan (username + qty_total) — bukan target klik, tidak bisa dibuka/diubah.
  const othersByProduct = useMemo(() => {
    const map = new Map()
    for (const e of othersOpen) {
      const list = map.get(e.product_name) || []
      list.push(e)
      map.set(e.product_name, list)
    }
    return map
  }, [othersOpen])

  function hintFor(productName) {
    const list = othersByProduct.get(productName)
    if (!list || !list.length) return null
    return `sudah dihitung ${list.map((e) => `${e.username}: ${Number(e.qty_total)}`).join(', ')}`
  }

  function openGroup(group) {
    const entry = openEntries.find((e) => e.product_name === group.name) || null
    setOpen({ group, entry })
    setQuery('')
  }

  function openFromEntry(entry) {
    const group = groups.find((g) => g.name === entry.product_name)
    if (group) { setOpen({ group, entry }); return }
    // Produk sudah tidak ada di `groups` (mis. dinonaktifkan job malam di tengah
    // hitungan) -- tanpa fallback ini, baris di "Hasil rak ini" jadi mati: diklik
    // tidak melakukan apa-apa. Bangun ulang group minimal dari entry.units supaya
    // entrinya tetap bisa dibuka/diubah/dihapus walau produknya sudah tidak aktif.
    if (entry.units?.length) {
      const fallback = {
        name: entry.product_name,
        category: '',
        brand: '',
        units: entry.units.map((u, i) => ({ ...u, unit_order: i })),
      }
      setOpen({ group: fallback, entry })
    }
  }

  async function upload() {
    setUploading(true)
    setUploadMsg('')
    setHapusMsg('')
    const { data, error } = await supabase.functions.invoke('upload-rak', { body: { rack } })
    if (error) setUploadMsg('err:Upload gagal — cek sinyal, coba lagi')
    else setUploadMsg(`ok:${data.uploaded} entri tersinkron ke pusat ✓`)
    await refresh()
    setUploading(false)
  }

  async function hapusEntri(ev, entry) {
    ev.stopPropagation()
    if (!window.confirm(
      `Hapus "${entry.product_name}" dari ${rack}?\n\n` +
        'Hitungannya dibuang dan tidak ikut ter-upload.',
    )) return
    setHapusBusy(entry.id)
    setHapusMsg('')
    try {
      await deleteEntry(entry.id)
      setHapusMsg('ok:Entri dihapus')
    } catch (err) {
      setHapusMsg(`err:${err.message}`)
    } finally {
      setHapusBusy(0)
    }
  }

  return (
    <>
      <div className="card">
        <div className="row">
          <span>{username} · <b>{rack}</b> <span className="badge">{openEntries.length} item</span></span>
          <button className="secondary" onClick={onChangeRack}>Ganti Rak</button>
        </div>
        {uploadMsg && (
          <p className={uploadMsg.startsWith('ok:') ? 'ok' : 'error'}>{uploadMsg.slice(uploadMsg.indexOf(':') + 1)}</p>
        )}
        <label>Cari produk</label>
        <input placeholder="ketik nama produk…" value={query} onChange={(e) => setQuery(e.target.value)} />
        {results.map((g) => {
          const hint = hintFor(g.name)
          return (
            <div className="entry" key={g.name} onClick={() => openGroup(g)}>
              <span>
                {g.name}
                {hint && <><br /><span className="muted">{hint}</span></>}
              </span>
              <span className="muted">{g.units.length} satuan</span>
            </div>
          )
        })}
        {query.trim() && !results.length && <p className="muted">Tidak ada — cek master / minta sync.</p>}
      </div>

      {open && (
        <CountForm
          key={open.entry?.id ?? open.group.name}
          group={open.group}
          initial={open.entry}
          colleagueHint={hintFor(open.group.name)}
          onCancel={() => setOpen(null)}
          onSave={async (units, expired) => {
            await saveEntry(open.group, units, expired, open.entry?.id)
            setOpen(null)
          }}
        />
      )}

      <div className="card">
        <h3>Hasil rak ini</h3>
        {hapusMsg && (
          <p className={hapusMsg.startsWith('ok:') ? 'ok' : 'error'}>{hapusMsg.slice(hapusMsg.indexOf(':') + 1)}</p>
        )}
        {!openEntries.length && <p className="muted">Belum ada.</p>}
        {openEntries.map((e) => (
          <div className="entry" key={e.id} onClick={() => openFromEntry(e)}>
            <span>{e.product_name}</span>
            <span className="entry-act">
              <span className="qty">{Number(e.qty_total)}</span>
              <button
                className="hapus"
                aria-label={`Hapus ${e.product_name}`}
                disabled={hapusBusy === e.id}
                onClick={(ev) => hapusEntri(ev, e)}
              >
                {hapusBusy === e.id ? '…' : '🗑'}
              </button>
            </span>
          </div>
        ))}
        <button className="primary" disabled={uploading || !openEntries.length} onClick={upload} style={{ marginTop: 12 }}>
          {uploading ? 'Mengirim…' : '⬆️ Upload'}
        </button>
      </div>
    </>
  )
}
