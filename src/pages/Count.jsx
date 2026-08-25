import { useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { filterGroups } from '../lib/groupProducts'
import { useEntries } from '../lib/useEntries'
import { useProducts } from '../lib/useProducts'
import CountForm from '../components/CountForm'

const BATAS_HASIL = 20

export default function Count({ session, rack, tanpaSinyal, onChangeRack }) {
  const { groups, produkMsg } = useProducts()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // { group, entry|null }
  const { entries, othersOpen, pending, antrianMsg, saveEntry, deleteEntry, refresh, kirimAntrian } =
    useEntries(rack, session)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploading, setUploading] = useState(false)
  const [hapusMsg, setHapusMsg] = useState('')
  const [hapusBusy, setHapusBusy] = useState(0)
  // Entri yang baru saja dihapus, ditahan untuk tombol Urungkan. Hapus di sini
  // permanen -- tanpa jaring ini satu ketukan salah berarti produk itu harus
  // dihitung ulang dari rak.
  const [terhapus, setTerhapus] = useState(null)
  const [urungBusy, setUrungBusy] = useState(false)
  const [lihatTerkirim, setLihatTerkirim] = useState(false)

  // Daftar dipotong supaya layar HP tidak dibanjiri ratusan baris. Jumlah penuhnya
  // ikut disimpan: memotong diam-diam bikin karyawan menyimpulkan produknya tidak
  // ada, lalu minta admin sync padahal cuma perlu mengetik satu kata lagi.
  const cocok = useMemo(() => filterGroups(groups, query), [groups, query])
  const results = useMemo(() => cocok.slice(0, BATAS_HASIL), [cocok])
  const openEntries = entries.filter((e) => !e.uploaded_at)
  // Entri yang sudah masuk ke pusat. Dulu disembunyikan sama sekali, jadi karyawan
  // tidak punya cara memastikan hitungannya benar-benar terkirim selain bertanya ke
  // admin. Read-only: yang terupload memang tidak boleh diubah dari sini.
  const terkirim = useMemo(
    () => entries.filter((e) => e.uploaded_at).sort((a, b) => (b.uploaded_at > a.uploaded_at ? 1 : -1)),
    [entries],
  )

  // Baris antrian ikut ditampilkan bersama baris server, ditandai "menunggu
  // sinyal". Kalau disembunyikan, karyawan mengira hitungannya hilang lalu
  // menghitung ulang produk yang sama. Baris server yang produknya sedang
  // diantre dibuang dari tampilan: angkanya sudah basi, yang benar yang di
  // antrian (satu entri terbuka per produk per orang).
  const daftar = useMemo(() => {
    const diantre = new Set(pending.map((p) => p.product_name))
    return [
      ...pending.map((p) => ({ ...p, menunggu: true })),
      ...openEntries.filter((e) => !diantre.has(e.product_name)),
    ]
  }, [pending, openEntries])

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
    const entry = daftar.find((e) => e.product_name === group.name) || null
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
    // Entri yang masih di antrian belum ada di DB, jadi `upload-rak` tidak akan
    // melihatnya. Kirim antrian dulu; kalau masih ada sisa, upload dibatalkan —
    // lebih baik tertunda daripada rak dilaporkan selesai padahal kurang.
    const { sisa } = await kirimAntrian()
    if (sisa) {
      setUploadMsg(`err:Masih ada ${sisa} hitungan menunggu sinyal — upload ditunda supaya tidak ada yang tertinggal.`)
      setUploading(false)
      return
    }
    const { data, error } = await supabase.functions.invoke('upload-rak', { body: { rack } })
    if (error) setUploadMsg('err:Upload gagal — cek sinyal, coba lagi')
    else setUploadMsg(`ok:${data.uploaded} entri tersinkron ke pusat ✓`)
    await refresh()
    setUploading(false)
  }

  async function hapusEntri(ev, entry) {
    ev.stopPropagation()
    setHapusBusy(entry.id)
    setHapusMsg('')
    setTerhapus(null)
    try {
      await deleteEntry(entry.id)
      // Tidak ada dialog konfirmasi: satu ketukan salah dibatalkan lewat Urungkan,
      // dan itu jauh lebih murah daripada memaksa semua orang menjawab "yakin?"
      // puluhan kali per rak.
      setTerhapus(entry)
      setHapusMsg('ok:Entri dihapus')
    } catch (err) {
      setHapusMsg(`err:${err.message}`)
    } finally {
      setHapusBusy(0)
    }
  }

  async function urungkanHapus() {
    if (!terhapus) return
    setUrungBusy(true)
    setHapusMsg('')
    try {
      const group = groups.find((g) => g.name === terhapus.product_name) || {
        name: terhapus.product_name,
        category: '',
        brand: '',
        units: (terhapus.units || []).map((u, i) => ({ ...u, unit_order: i })),
      }
      await saveEntry(group, terhapus.units, terhapus.expired_date, null)
      setTerhapus(null)
      setHapusMsg('ok:Entri dikembalikan')
    } catch (err) {
      setHapusMsg(`err:${err.message}`)
    } finally {
      setUrungBusy(false)
    }
  }

  return (
    <>
      <div className="card">
        <p className="section-title">
          <span>{rack}</span>
          <span className="spacer" />
          <button className="secondary" onClick={onChangeRack}>Ganti rak</button>
        </p>
        {uploadMsg && (
          <p className={uploadMsg.startsWith('ok:') ? 'ok' : 'error'}>{uploadMsg.slice(uploadMsg.indexOf(':') + 1)}</p>
        )}
        {pending.length > 0 && (
          <p className="error">
            ⏳ {pending.length} hitungan tersimpan di HP, belum sampai ke pusat. Aman —
            terkirim sendiri begitu sinyal balik. Jangan hapus aplikasi dulu.
          </p>
        )}
        {tanpaSinyal && (
          <p className="muted">
            Daftar di bawah dibaca dari simpanan HP, jadi hitungan rekan yang masuk
            barusan belum tentu kelihatan.
          </p>
        )}
        {antrianMsg && <p className="error">{antrianMsg}</p>}
        <div className="search">
          <span className="search-ico" aria-hidden="true">🔍</span>
          <input
            aria-label="Cari produk"
            placeholder="Cari produk…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {results.map((g) => {
          const hint = hintFor(g.name)
          return (
            <div className="entry" key={g.name} onClick={() => openGroup(g)}>
              <span className="name">
                {g.name}
                {hint && <><br /><span className="muted">{hint}</span></>}
              </span>
              <span className="muted" style={{ whiteSpace: 'nowrap' }}>{g.units.length} satuan</span>
            </div>
          )
        })}
        {cocok.length > BATAS_HASIL && (
          <p className="muted" style={{ marginTop: 10 }}>
            Menampilkan {BATAS_HASIL} dari {cocok.length} produk yang cocok — ketik lebih
            spesifik untuk mempersempit.
          </p>
        )}
        {produkMsg && <p className="error" style={{ marginTop: 12 }}>{produkMsg}</p>}
        {query.trim() && !results.length && (
          <p className="muted" style={{ marginTop: 14 }}>
            {groups.length
              ? 'Tidak ada — cek master / minta sync.'
              : 'Daftar produk belum siap, tunggu sebentar…'}
          </p>
        )}
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
        <p className="section-title">
          <span>Hasil rak ini</span>
          <span className="spacer" />
          <span className="badge">{daftar.length} item</span>
        </p>
        {hapusMsg && (
          <p className={hapusMsg.startsWith('ok:') ? 'ok' : 'error'}>
            {hapusMsg.slice(hapusMsg.indexOf(':') + 1)}
            {terhapus && (
              <>
                {' '}
                <button className="link" disabled={urungBusy} onClick={urungkanHapus}>
                  {urungBusy ? 'Mengembalikan…' : `Urungkan "${terhapus.product_name}"`}
                </button>
              </>
            )}
          </p>
        )}
        {!daftar.length && <p className="muted">Belum ada. Cari produk di atas untuk mulai hitung.</p>}
        {daftar.map((e) => (
          <div className="entry" key={e.id} onClick={() => openFromEntry(e)}>
            <span className="name">
              {e.product_name}
              {e.menunggu && <><br /><span className="muted">⏳ menunggu sinyal — tersimpan di HP</span></>}
            </span>
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
      </div>

      {terkirim.length > 0 && (
        <div className="card">
          <button className="disclose" aria-expanded={lihatTerkirim} onClick={() => setLihatTerkirim((v) => !v)}>
            <span>Sudah terkirim ke pusat</span>
            <span className="spacer" />
            <span className="badge green">{terkirim.length}</span>
            {/* Segitiga (U+25BE/U+25B8) dipilih karena ada di hampir semua font Android;
                U+2304 yang dipakai sebelumnya tidak, dan tampil kosong. */}
            <span className="arw" aria-hidden="true">{lihatTerkirim ? '▾' : '▸'}</span>
          </button>
          {lihatTerkirim && (
            <>
              <p className="muted" style={{ marginTop: 10 }}>
                Sudah terkunci — perbaikannya lewat admin, bukan dari sini.
              </p>
              {terkirim.map((e) => (
                <div className="entry statis" key={e.id}>
                  <span className="name">{e.product_name}</span>
                  <span className="qty">{Number(e.qty_total)}</span>
                </div>
              ))}
            </>
          )}
        </div>
      )}
      {tanpaSinyal && !terkirim.length && (
        <p className="muted" style={{ textAlign: 'center' }}>
          Daftar "sudah terkirim" baru bisa dilihat kalau ada sinyal.
        </p>
      )}

      {/* Upload nempel di bawah layar: setelah menghitung 30 produk, tombolnya tidak
          perlu di-scroll dan jumlah entri selalu kelihatan. */}
      <div className="actionbar">
        <div className="actionbar-in">
          <button
            className="primary"
            disabled={uploading || tanpaSinyal || !daftar.length}
            onClick={upload}
          >
            {tanpaSinyal
              ? `📴 ${daftar.length} entri — upload nanti kalau ada sinyal`
              : uploading
                ? 'Mengirim…'
                : daftar.length
                  ? `⬆️ Upload ${daftar.length} entri`
                  : '⬆️ Upload'}
          </button>
        </div>
      </div>
    </>
  )
}
