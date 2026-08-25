// Rekap entri untuk dashboard admin. Semua fungsi murni.
const wibDate = (d) => new Date(d).toLocaleDateString('sv-SE', { timeZone: 'Asia/Jakarta' })

// Kapan entri terakhir disentuh: pakai updated_at kalau lebih baru dari created_at (edit), else created_at.
const touchedAt = (e) => (e.updated_at && e.updated_at > e.created_at ? e.updated_at : e.created_at)

export function rackProgress(entries, rackNames) {
  const byRack = new Map(rackNames.map((r) => [r, { rack: r, open: 0, uploaded: 0, lastAt: null }]))
  for (const e of entries) {
    const row = byRack.get(e.rack)
    if (!row) continue
    if (e.uploaded_at) row.uploaded++
    else row.open++
    const at = touchedAt(e)
    if (!row.lastAt || at > row.lastAt) row.lastAt = at
  }
  return [...byRack.values()]
}

export function staffActivity(entries, now = new Date()) {
  const today = wibDate(now)
  const byUser = new Map()
  for (const e of entries) {
    let row = byUser.get(e.username)
    if (!row) byUser.set(e.username, (row = { username: e.username, today: 0, total: 0, open: 0, lastAt: null }))
    row.total++
    if (!e.uploaded_at) row.open++
    const at = touchedAt(e)
    if (wibDate(at) === today) row.today++
    if (!row.lastAt || at > row.lastAt) row.lastAt = at
  }
  return [...byUser.values()].sort((a, b) => (b.lastAt || '').localeCompare(a.lastAt || ''))
}

export function latestEntries(entries, n = 20) {
  return [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, n)
}

// --- Mutasi barang -----------------------------------------------------------
//
// Dashboard versi pertama cuma membaca count_entries, jadi surat jalan (Barang
// Datang, Isi Ulang, Pindah, Barang Rusak) tidak kelihatan sama sekali di halaman
// admin. Dua fungsi di bawah ini menutup lubang itu.
//
// Sengaja dipisah dari staffActivity/rackProgress: mutasi dikelompokkan per JENIS
// (bukan per rak) dan tidak punya konsep "progres rak", jadi menumpangkan keduanya
// ke satu fungsi cuma bikin keduanya penuh percabangan.

// Urutan tetap supaya kartunya tidak melompat-lompat saat ada jenis yang kosong.
export const JENIS_URUT = ['Datang', 'Isi Ulang', 'Pindah', 'Rusak']

export function mutasiRingkas(moves, now = new Date()) {
  const today = wibDate(now)
  const byJenis = new Map(
    JENIS_URUT.map((j) => [j, { jenis: j, today: 0, total: 0, open: 0, qty: 0, lastAt: null }]),
  )
  for (const m of moves) {
    let row = byJenis.get(m.jenis)
    // Jenis yang belum dikenal (mis. ditambah belakangan) tetap ditampilkan, bukan
    // dibuang diam-diam -- baris yang hilang dari dashboard tidak pernah ketahuan.
    if (!row) byJenis.set(m.jenis, (row = { jenis: m.jenis, today: 0, total: 0, open: 0, qty: 0, lastAt: null }))
    row.total++
    row.qty += Number(m.qty_total) || 0
    if (!m.uploaded_at) row.open++
    const at = touchedAt(m)
    if (wibDate(at) === today) row.today++
    if (!row.lastAt || at > row.lastAt) row.lastAt = at
  }
  return [...byJenis.values()]
}

export function latestMoves(moves, n = 15) {
  return [...moves].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, n)
}
