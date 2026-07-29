import { describe, it, expect } from 'vitest'
import { rackProgress, staffActivity, latestEntries } from './adminStats'

// created_at UTC; 2026-07-28T18:00Z = 2026-07-29 01:00 WIB
const entries = [
  { username: 'sari', rack: 'Rak 1', product_name: 'Mika DP 7C', qty_total: 10, created_at: '2026-07-28T18:00:00Z', uploaded_at: null },
  { username: 'sari', rack: 'Rak 1', product_name: 'Mentega Simas', qty_total: 5, created_at: '2026-07-28T10:00:00Z', uploaded_at: '2026-07-28T11:00:00Z' },
  { username: 'budi', rack: 'Rak 2', product_name: 'Tepung Segitiga', qty_total: 3, created_at: '2026-07-28T09:00:00Z', uploaded_at: null },
]
// "sekarang" = 2026-07-29 08:00 WIB
const now = new Date('2026-07-29T01:00:00Z')

describe('rackProgress', () => {
  it('hitung open/uploaded per rak, rak kosong ikut', () => {
    const p = rackProgress(entries, ['Rak 1', 'Rak 2', 'Rak 3'])
    expect(p).toHaveLength(3)
    expect(p[0]).toEqual({ rack: 'Rak 1', open: 1, uploaded: 1, lastAt: '2026-07-28T18:00:00Z' })
    expect(p[1].open).toBe(1)
    expect(p[2]).toEqual({ rack: 'Rak 3', open: 0, uploaded: 0, lastAt: null })
  })
})

describe('staffActivity', () => {
  it('today pakai tanggal WIB, urut lastAt desc', () => {
    const a = staffActivity(entries, now)
    expect(a[0]).toEqual({ username: 'sari', today: 1, total: 2, lastAt: '2026-07-28T18:00:00Z' })
    expect(a[1].username).toBe('budi')
    expect(a[1].today).toBe(0)
  })
})

describe('latestEntries', () => {
  it('urut created_at desc, maks n', () => {
    const l = latestEntries(entries, 2)
    expect(l).toHaveLength(2)
    expect(l[0].product_name).toBe('Mika DP 7C')
  })
})
