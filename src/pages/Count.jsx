import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { groupProducts, filterGroups } from '../lib/groupProducts'
import { useEntries } from '../lib/useEntries'
import CountForm from '../components/CountForm'

export default function Count({ session, username, rack, onChangeRack }) {
  const [groups, setGroups] = useState([])
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // { group, entry|null }
  const { entries, saveEntry, deleteEntry, refresh } = useEntries(rack, session)
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

  function openGroup(group) {
    const entry = openEntries.find((e) => e.product_name === group.name) || null
    setOpen({ group, entry })
    setQuery('')
  }

  function openFromEntry(entry) {
    const group = groups.find((g) => g.name === entry.product_name)
    if (group) setOpen({ group, entry })
  }

  async function upload() {
    setUploading(true)
    setUploadMsg('')
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
        {results.map((g) => (
          <div className="entry" key={g.name} onClick={() => openGroup(g)}>
            <span>{g.name}</span><span className="muted">{g.units.length} satuan</span>
          </div>
        ))}
        {query.trim() && !results.length && <p className="muted">Tidak ada — cek master / minta sync.</p>}
      </div>

      {open && (
        <CountForm
          key={open.entry?.id ?? open.group.name}
          group={open.group}
          initial={open.entry}
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
