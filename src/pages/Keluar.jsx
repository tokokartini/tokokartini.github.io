import { useEffect, useMemo, useState } from 'react'
import { supabase } from '../lib/supabase'
import { filterGroups } from '../lib/groupProducts'
import { useProducts } from '../lib/useProducts'
import { useMovements } from '../lib/useMovements'
import { useRacks } from '../lib/racks'
import { modeOf, lokasiPilihan, lokasiAwal, siapLanjut, seringDipakai } from '../lib/mutasi'
import CountForm from '../components/CountForm'

const BATAS_HASIL = 20

// Halaman surat jalan: barang datang, isi ulang display, pindah antar gudang.
// Tiga-tiganya alur yang sama -- yang berbeda cuma sisi lokasi mana yang sudah
// terkunci -- jadi satu halaman, aturannya di src/lib/mutasi.js.
export default function Keluar({ session, modeKey, tanpaSinyal, onSelesai }) {
  const mode = modeOf(modeKey)
  const awal = lokasiAwal(mode)

  const racks = useRacks()
  const [from, setFrom] = useState(awal.from)
  const [to, setTo] = useState(awal.to)
  const [nota, setNota] = useState('')
  const [langkah, setLangkah] = useState('lokasi')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(null) // { group, item|null }
  const [sering, setSering] = useState([])
  const [kirimMsg, setKirimMsg] = useState('')
  const [kirimOk, setKirimOk] = useState('')
  const [kirimBusy, setKirimBusy] = useState(false)
  const [hapusMsg, setHapusMsg] = useState('')
  const [hapusBusy, setHapusBusy] = useState(0)
  // Baris yang baru dicoret, ditahan untuk tombol Urungkan -- hapus di sini permanen.
  const [terhapus, setTerhapus] = useState(null)
  const [urungBusy, setUrungBusy] = useState(false)

  const { groups, produkMsg } = useProducts()
  const { items, pending, antrianMsg, saveItem, deleteItem, kirimAntrian } =
    useMovements(from, to, session)

  // Daftar "sering diisi ulang": dihitung dari riwayat 30 hari, bukan daftar yang
  // harus dirawat manual. Minggu pertama memang kosong -- itu wajar, bukan galat,
  // jadi tidak ada pesan apa pun saat hasilnya nihil.
  useEffect(() => {
    if (mode.key !== 'display') return
    const sejak = new Date(Date.now() - 30 * 86400000).toISOString()
    supabase
      .from('movements')
      .select('product_name')
      .eq('jenis', mode.jenis)
      .gte('created_at', sejak)
      .limit(1000)
      .then(({ data }) => setSering(seringDipakai(data)))
  }, [mode.key, mode.jenis])

  const pilihan = useMemo(() => lokasiPilihan(mode, racks), [mode, racks])
  const cocok = useMemo(() => filterGroups(groups, query), [groups, query])
  const hasil = useMemo(() => cocok.slice(0, BATAS_HASIL), [cocok])
  const seringGroups = useMemo(() => {
    if (mode.key !== 'display') return []
    return sering.map((s) => groups.find((g) => g.name === s.product_name)).filter(Boolean)
  }, [sering, groups, mode.key])

  const siap = siapLanjut(from, to)
  const rute = `${from} › ${to}`

  // Baris antrian ikut ditampilkan bersama baris server, ditandai "menunggu sinyal".
  // Kalau disembunyikan, petugas mengira barangnya belum tercatat lalu mengetiknya
  // dua kali. Baris server yang produknya sedang diantre dibuang dari tampilan:
  // angkanya sudah basi, yang benar yang di antrian.
  const daftar = useMemo(() => {
    const diantre = new Set(pending.map((p) => p.product_name))
    return [
      ...pending.map((p) => ({ ...p, menunggu: true })),
      ...items.filter((i) => !diantre.has(i.product_name)),
    ]
  }, [pending, items])

  function pilihLokasi(sisi, nama) {
    setKirimOk('')
    if (sisi === 'from') {
      setFrom(nama)
      if (to === nama) setTo('')
    } else {
      setTo(nama)
    }
  }

  function bukaProduk(group) {
    const adaItem = daftar.find((i) => i.product_name === group.name) || null
    setOpen({ group, item: adaItem })
    setQuery('')
  }

  function bukaDariItem(item) {
    const group = groups.find((g) => g.name === item.product_name)
    if (group) { setOpen({ group, item }); return }
    // Produk sudah tidak aktif (mis. dinonaktifkan job malam di tengah bongkar
    // muat). Tanpa fallback ini barisnya jadi mati -- diklik tidak terjadi apa-apa.
    if (item.units?.length) {
      setOpen({
        group: { name: item.product_name, category: '', brand: '', units: item.units.map((u, i) => ({ ...u, unit_order: i })) },
        item,
      })
    }
  }

  async function hapus(item) {
    setHapusMsg('')
    setHapusBusy(item.id)
    setTerhapus(null)
    try {
      await deleteItem(item.id)
      setTerhapus(item)
    } catch (e) {
      setHapusMsg(e.message)
    }
    setHapusBusy(0)
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
      await saveItem(group, terhapus.units, mode.jenis, terhapus.nota || nota, null)
      setTerhapus(null)
    } catch (e) {
      setHapusMsg(e.message)
    }
    setUrungBusy(false)
  }

  async function kirim() {
    setKirimBusy(true)
    setKirimMsg('')
    setKirimOk('')
    // Baris yang masih di antrian belum ada di DB, jadi `upload-mutasi` tidak akan
    // melihatnya. Kirim antrian dulu; kalau masih ada sisa, pengiriman dibatalkan --
    // lebih baik tertunda daripada surat jalan dilaporkan lengkap padahal kurang.
    const { sisa } = await kirimAntrian()
    if (sisa) {
      setKirimMsg(`Masih ada ${sisa} barang menunggu sinyal — pengiriman ditunda supaya tidak ada yang tertinggal.`)
      setKirimBusy(false)
      return
    }
    try {
      const { data, error } = await supabase.functions.invoke('upload-mutasi', { body: { from, to } })
      if (error) throw error
      if (data?.error) throw new Error(data.error)
      setKirimOk(`${data.uploaded} barang tercatat sebagai ${mode.jenis}.`)
      setNota('')
      setLangkah('lokasi')
      setFrom(awal.from)
      setTo(awal.to)
    } catch {
      setKirimMsg('Gagal kirim — cek sinyal, lalu coba lagi. Barangnya masih tersimpan.')
    }
    setKirimBusy(false)
  }

  // ── Langkah 1: lokasi ────────────────────────────────────────────────────
  if (langkah === 'lokasi') {
    const sisiPilih = mode.kunci === 'to' ? 'from' : 'to'
    return (
      <>
        {kirimOk && <p className="ok">{kirimOk}</p>}

        {mode.kunci ? (
          <>
            <div className="card">
              <p className="section-title">{mode.tetapLabel}</p>
              <div className="fixed-loc">
                <span className="ico" aria-hidden="true">{mode.tetapIco}</span>
                {mode.tetap}
                <span className="tail">terkunci</span>
              </div>
            </div>
            <div className="card">
              <p className="section-title">{mode.tanya}</p>
              <RackList
                daftar={pilihan}
                dipilih={sisiPilih === 'from' ? from : to}
                onPilih={(nama) => pilihLokasi(sisiPilih, nama)}
              />
            </div>
            {mode.nota && (
              <div className="card">
                <p className="section-title">Nota <span className="spacer" /><span className="muted">boleh kosong</span></p>
                <input
                  value={nota}
                  onChange={(e) => setNota(e.target.value)}
                  placeholder="Nama supplier atau nomor nota"
                  autoComplete="off"
                />
              </div>
            )}
          </>
        ) : (
          <>
            <div className="card">
              <p className="section-title">Dari gudang</p>
              <RackList daftar={pilihan} dipilih={from} onPilih={(nama) => pilihLokasi('from', nama)} />
            </div>
            <div className="card">
              <p className="section-title">
                Ke gudang
                {!from && <><span className="spacer" /><span className="muted">pilih asal dulu</span></>}
              </p>
              <RackList
                daftar={pilihan}
                dipilih={to}
                terkunci={from}
                onPilih={(nama) => pilihLokasi('to', nama)}
              />
            </div>
          </>
        )}

        <div className="card">
          <button className="secondary" onClick={onSelesai}>Kembali ke menu</button>
        </div>

        <div className="actionbar">
          <div className="actionbar-in">
            <button className="primary" disabled={!siap} onClick={() => setLangkah('isi')}>
              {siap ? 'Lanjut, pilih barang' : 'Pilih lokasi dulu'}
            </button>
          </div>
        </div>
      </>
    )
  }

  // ── Langkah 2: isi surat jalan ───────────────────────────────────────────
  return (
    <>
      <div className="card">
        <p className="section-title">
          Cari barang
          <span className="spacer" />
          <button className="link" onClick={() => setLangkah('lokasi')}>Ganti lokasi</button>
        </p>
        {produkMsg && <p className="error">{produkMsg}</p>}
        <div className="search">
          <span className="search-ico" aria-hidden="true">🔍</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ketik nama produk atau SKU"
            autoComplete="off"
          />
        </div>

        {query ? (
          hasil.length ? (
            <div style={{ marginTop: 8 }}>
              {hasil.map((g) => <BarisProduk key={g.name} group={g} items={daftar} onKlik={bukaProduk} />)}
              {cocok.length > BATAS_HASIL && (
                <p className="muted" style={{ marginTop: 10 }}>
                  Menampilkan {BATAS_HASIL} dari {cocok.length} produk yang cocok — ketik
                  lebih spesifik untuk mempersempit.
                </p>
              )}
            </div>
          ) : (
            <p className="muted" style={{ marginTop: 12 }}>Tidak ada produk yang cocok.</p>
          )
        ) : seringGroups.length ? (
          <>
            <p className="section-title" style={{ marginTop: 16 }}>Sering diisi ulang</p>
            {seringGroups.map((g) => <BarisProduk key={g.name} group={g} items={daftar} onKlik={bukaProduk} />)}
          </>
        ) : (
          <p className="muted" style={{ marginTop: 12 }}>Ketik nama produknya untuk mulai.</p>
        )}
      </div>

      <div className="card">
        <p className="section-title">
          Surat jalan
          <span className="spacer" />
          <span className="badge green">{daftar.length} barang</span>
        </p>
        <p className="muted" style={{ marginBottom: 12 }}>{rute}</p>
        {pending.length > 0 && (
          <p className="error">
            ⏳ {pending.length} barang tersimpan di HP, belum sampai ke pusat. Aman —
            terkirim sendiri begitu sinyal balik. Jangan hapus aplikasi dulu.
          </p>
        )}
        {antrianMsg && <p className="error">{antrianMsg}</p>}
        {hapusMsg && <p className="error">{hapusMsg}</p>}
        {terhapus && (
          <p className="ok">
            "{terhapus.product_name}" dicoret.{' '}
            <button className="link" disabled={urungBusy} onClick={urungkanHapus}>
              {urungBusy ? 'Mengembalikan…' : 'Urungkan'}
            </button>
          </p>
        )}
        {daftar.length === 0 && <p className="muted">Belum ada barang. Pilih produk di atas, lalu isi jumlahnya.</p>}
        {daftar.map((it) => (
          <div key={it.id} className="entry" onClick={() => bukaDariItem(it)}>
            <span className="name">
              {it.product_name}
              <br />
              <span className="muted">
                {it.menunggu ? '⏳ menunggu sinyal — tersimpan di HP' : rincianSingkat(it.units)}
              </span>
            </span>
            <span className="entry-act">
              <span className="qty">{Number(it.qty_total)}</span>
              <button
                className="hapus"
                disabled={hapusBusy === it.id}
                aria-label={`Hapus ${it.product_name}`}
                onClick={(e) => { e.stopPropagation(); hapus(it) }}
              >
                🗑
              </button>
            </span>
          </div>
        ))}
      </div>

      {kirimMsg && <p className="error">{kirimMsg}</p>}

      <div className="actionbar">
        <div className="actionbar-in">
          <button
            className="primary"
            disabled={!daftar.length || kirimBusy || tanpaSinyal}
            onClick={kirim}
          >
            {tanpaSinyal
              ? `📴 ${daftar.length} barang — kirim nanti kalau ada sinyal`
              : kirimBusy
                ? 'Mengirim…'
                : daftar.length
                  ? `Kirim ${daftar.length} barang`
                  : 'Belum ada barang'}
          </button>
        </div>
      </div>

      {open && (
        <CountForm
          group={open.group}
          initial={open.item}
          subtitle={rute}
          showExpired={false}
          saveLabel="Simpan"
          onSave={async (units) => {
            await saveItem(open.group, units, mode.jenis, nota, open.item?.id)
            setOpen(null)
          }}
          onCancel={() => setOpen(null)}
        />
      )}
    </>
  )
}

function RackList({ daftar, dipilih, terkunci, onPilih }) {
  if (!daftar.length) return <p className="muted">Memuat daftar lokasi…</p>
  return (
    <div className="rack-list">
      {daftar.map((r) => (
        <button
          type="button"
          key={r}
          className={`rack-opt${r === dipilih ? ' on' : ''}`}
          aria-pressed={r === dipilih}
          disabled={r === terkunci}
          onClick={() => onPilih(r)}
        >
          <span className="dot" aria-hidden="true" />
          {r}
          {r === terkunci && <span className="tail">lokasi asal</span>}
        </button>
      ))}
    </div>
  )
}

function BarisProduk({ group, items, onKlik }) {
  const sudah = items.find((i) => i.product_name === group.name)
  return (
    <div className="entry" onClick={() => onKlik(group)}>
      <span className="name">
        {group.name}
        <br />
        <span className="muted">{group.units.map((u) => `${u.variant} ×${u.mult}`).join(' · ')}</span>
      </span>
      {sudah ? <span className="badge soft">sudah {Number(sudah.qty_total)}</span> : <span className="muted">＋</span>}
    </div>
  )
}

// Ringkasan satuan asli untuk baris daftar, mis. "2 Krtn + 5 Pack". Versi lengkap
// yang masuk sheet disusun rincianText() di functions/upload-mutasi/rows.ts.
function rincianSingkat(units) {
  if (!units) return ''
  return [...units]
    .filter((u) => Number(u.qty) !== 0)
    .sort((a, b) => b.mult - a.mult)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}
