import { describe, it, expect } from 'vitest'
import { rackProgress, staffActivity, latestEntries } from './adminStats'

// created_at UTC; 2026-07-28T18:00Z = 2026-07-29 01:00 WIB
// Fixture sengaja TIDAK berurutan by created_at, biar latestEntries beneran harus sort.
// Entri budi juga di-edit belakangan (updated_at > created_at) buat nguji touchedAt.
const entries = [
  { username: 'budi', rack: 'Rak 2', product_name: 'Tepung Segitiga', qty_total: 3, created_at: '2026-07-28T09:00:00Z', updated_at: '2026-07-29T00:30:00Z', uploaded_at: null },
  { username: 'sari', rack: 'Rak 1', product_name: 'Mentega Simas', qty_total: 5, created_at: '2026-07-28T10:00:00Z', updated_at: null, uploaded_at: '2026-07-28T11:00:00Z' },
  { username: 'sari', rack: 'Rak 1', product_name: 'Mika DP 7C', qty_total: 10, created_at: '2026-07-28T18:00:00Z', updated_at: '2026-07-28T18:00:00Z', uploaded_at: null },
]
// "sekarang" = 2026-07-29 08:00 WIB
const now = new Date('2026-07-29T01:00:00Z')

describe('rackProgress', () => {
  it('hitung open/uploaded per rak, rak kosong ikut', () => {
    const p = rackProgress(entries, ['Rak 1', 'Rak 2', 'Rak 3'])
    expect(p).toHaveLength(3)
    expect(p[0]).toEqual({ rack: 'Rak 1', open: 1, uploaded: 1, lastAt: '2026-07-28T18:00:00Z' })
    expect(p[2]).toEqual({ rack: 'Rak 3', open: 0, uploaded: 0, lastAt: null })
  })

  it('lastAt pakai updated_at kalau entri diedit belakangan', () => {
    const p = rackProgress(entries, ['Rak 1', 'Rak 2', 'Rak 3'])
    // entri budi di Rak 2 di-edit di 2026-07-29T00:30Z, lebih baru dari created_at-nya
    expect(p[1]).toEqual({ rack: 'Rak 2', open: 1, uploaded: 0, lastAt: '2026-07-29T00:30:00Z' })
  })
})

describe('staffActivity', () => {
  it('today pakai tanggal WIB, urut lastAt desc', () => {
    const a = staffActivity(entries, now)
    // sari: dua entri, satu di antaranya (Mika DP 7C) jatuh di tanggal WIB hari ini
    const sari = a.find((x) => x.username === 'sari')
    expect(sari).toEqual({ username: 'sari', today: 1, total: 2, lastAt: '2026-07-28T18:00:00Z' })
  })

  it('edit (updated_at > created_at) geser lastAt & hitungan today', () => {
    const a = staffActivity(entries, now)
    const budi = a.find((x) => x.username === 'budi')
    // created_at budi (2026-07-28T09:00Z) bukan hari ini, tapi updated_at (2026-07-29T00:30Z) iya
    expect(budi).toEqual({ username: 'budi', today: 1, total: 1, lastAt: '2026-07-29T00:30:00Z' })
    // karena lastAt budi (habis diedit) lebih baru dari lastAt sari, budi naik ke urutan pertama
    expect(a[0].username).toBe('budi')
  })
})

describe('latestEntries', () => {
  it('urut created_at desc (bukan urutan fixture), maks n', () => {
    const l = latestEntries(entries, 2)
    expect(l).toHaveLength(2)
    expect(l[0].product_name).toBe('Mika DP 7C')
    expect(l[1].product_name).toBe('Mentega Simas')
  })
})
