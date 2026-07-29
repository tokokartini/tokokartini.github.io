// Rekap entri untuk dashboard admin. Semua fungsi murni.
const wibDate = (d) => new Date(d).toLocaleDateString('sv-SE', { timeZone: 'Asia/Jakarta' })

export function rackProgress(entries, rackNames) {
  const byRack = new Map(rackNames.map((r) => [r, { rack: r, open: 0, uploaded: 0, lastAt: null }]))
  for (const e of entries) {
    const row = byRack.get(e.rack)
    if (!row) continue
    if (e.uploaded_at) row.uploaded++
    else row.open++
    if (!row.lastAt || e.created_at > row.lastAt) row.lastAt = e.created_at
  }
  return [...byRack.values()]
}

export function staffActivity(entries, now = new Date()) {
  const today = wibDate(now)
  const byUser = new Map()
  for (const e of entries) {
    let row = byUser.get(e.username)
    if (!row) byUser.set(e.username, (row = { username: e.username, today: 0, total: 0, lastAt: null }))
    row.total++
    if (wibDate(e.created_at) === today) row.today++
    if (!row.lastAt || e.created_at > row.lastAt) row.lastAt = e.created_at
  }
  return [...byUser.values()].sort((a, b) => (b.lastAt || '').localeCompare(a.lastAt || ''))
}

export function latestEntries(entries, n = 20) {
  return [...entries].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, n)
}
