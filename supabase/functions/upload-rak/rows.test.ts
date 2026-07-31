// Menguji pemilih baris Log: tiap entri jadi SATU baris dalam satuan dasar,
// qty diambil dari kolom qty_total (bukan dijumlah ulang di sini).
import { describe, it, expect } from 'vitest'
import { baseUnitOf, buildLogRows, rincianText, wib } from './rows.ts'

const KERTAS = {
  updated_at: '2026-07-30T01:01:53.000+00:00',
  username: 'naruto',
  rack: 'Rak 5',
  product_name: 'Kertas Nasi Putih MG 25*27',
  units: [
    { sku: 'KTN-0008-G', variant: 'Krtn (50 Pack)', mult: 50, qty: 1 },
    { sku: 'KTN-0008-3', variant: 'Pack', mult: 1, qty: 25 },
  ],
  qty_total: 75,
  expired_date: null,
}

describe('wib', () => {
  it('geser +7 jam, format YYYY-MM-DD HH:MM:SS', () => {
    expect(wib('2026-07-30T01:01:53.000+00:00')).toBe('2026-07-30 08:01:53')
  })

  it('lewat tengah malam UTC tetap benar', () => {
    expect(wib('2026-07-29T20:00:00.000+00:00')).toBe('2026-07-30 03:00:00')
  })
})

describe('baseUnitOf', () => {
  it('pilih satuan dengan mult 1', () => {
    expect(baseUnitOf(KERTAS.units)?.sku).toBe('KTN-0008-3')
  })

  it('tanpa mult 1, pilih mult terkecil', () => {
    const units = [
      { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 2 },
      { sku: 'X-2', variant: 'Trs', mult: 5, qty: 3 },
    ]
    expect(baseUnitOf(units)?.sku).toBe('X-2')
  })

  it('units kosong -> null', () => {
    expect(baseUnitOf([])).toBeNull()
  })
})

describe('rincianText', () => {
  it('gabung tiap satuan, urut mult besar ke kecil', () => {
    expect(rincianText(KERTAS.units)).toBe('1 Krtn (50 Pack) + 25 Pack')
  })

  it('urutan units acak tetap keluar besar ke kecil', () => {
    expect(
      rincianText([
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 5 },
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 2 },
        { sku: 'X-2', variant: 'Pack', mult: 5, qty: 3 },
      ]),
    ).toBe('2 Krtn + 3 Pack + 5 Pcs')
  })

  it('satuan qty 0 tidak ikut ditulis', () => {
    expect(
      rincianText([
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 0 },
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 7 },
      ]),
    ).toBe('7 Pcs')
  })

  it('semua qty 0 -> teks kosong', () => {
    expect(
      rincianText([
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 0 },
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 0 },
      ]),
    ).toBe('')
  })

  it('units null atau kosong -> teks kosong', () => {
    expect(rincianText(null)).toBe('')
    expect(rincianText([])).toBe('')
  })

  it('qty negatif tetap ditulis (input tidak dijaga form, DB cuma cek total)', () => {
    expect(
      rincianText([
        { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 1 },
        { sku: 'X-3', variant: 'Pcs', mult: 1, qty: -3 },
      ]),
    ).toBe('1 Krtn + -3 Pcs')
  })

  it('tidak mengubah urutan array aslinya', () => {
    const units = [
      { sku: 'X-3', variant: 'Pcs', mult: 1, qty: 5 },
      { sku: 'X-G', variant: 'Krtn', mult: 40, qty: 2 },
    ]
    rincianText(units)
    expect(units.map((u) => u.sku)).toEqual(['X-3', 'X-G'])
  })
})

describe('buildLogRows', () => {
  it('entri multi-satuan jadi satu baris 9 kolom, rincian + qty dasar', () => {
    const { rows, skipped } = buildLogRows([KERTAS])
    expect(skipped).toEqual([])
    expect(rows).toEqual([
      [
        '2026-07-30 08:01:53',
        'naruto',
        'Rak 5',
        'Kertas Nasi Putih MG 25*27',
        '1 Krtn (50 Pack) + 25 Pack',
        75,
        'Pack',
        '',
        'KTN-0008-3',
      ],
    ])
  })

  it('tanpa mult 1, pakai satuan mult terkecil', () => {
    const { rows } = buildLogRows([
      {
        ...KERTAS,
        units: [
          { sku: 'PKG-0094-G', variant: 'Krtn (20 Trs)', mult: 20, qty: 1 },
          { sku: 'PKG-0094-2', variant: 'Trs', mult: 4, qty: 2 },
        ],
        qty_total: 28,
      },
    ])
    expect(rows[0][4]).toBe('1 Krtn (20 Trs) + 2 Trs')
    expect(rows[0][5]).toBe(28)
    expect(rows[0][6]).toBe('Trs')
    expect(rows[0][8]).toBe('PKG-0094-2')
  })

  it('qty_total 0 tetap ditulis satu baris, rincian kosong', () => {
    const { rows } = buildLogRows([
      { ...KERTAS, units: [{ sku: 'KTN-0008-3', variant: 'Pack', mult: 1, qty: 0 }], qty_total: 0 },
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0][4]).toBe('')
    expect(rows[0][5]).toBe(0)
  })

  it('qty_total null jadi 0, bukan baris hilang', () => {
    const { rows } = buildLogRows([{ ...KERTAS, qty_total: null }])
    expect(rows).toHaveLength(1)
    expect(rows[0][5]).toBe(0)
  })

  it('units kosong atau null dilewati dan dilaporkan', () => {
    const { rows, skipped } = buildLogRows([
      { ...KERTAS, units: [] },
      { ...KERTAS, product_name: 'Tanpa Satuan', units: null },
      KERTAS,
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0][3]).toBe('Kertas Nasi Putih MG 25*27')
    expect(skipped).toEqual(['Kertas Nasi Putih MG 25*27', 'Tanpa Satuan'])
  })

  it('expired_date ditulis apa adanya kalau ada', () => {
    const { rows } = buildLogRows([{ ...KERTAS, expired_date: '2027-01-31' }])
    expect(rows[0][7]).toBe('2027-01-31')
  })

  it('tiap baris tepat 9 kolom', () => {
    const { rows } = buildLogRows([KERTAS])
    expect(rows[0]).toHaveLength(9)
  })

  it('urutan baris sama dengan urutan entri', () => {
    const { rows } = buildLogRows([
      { ...KERTAS, product_name: 'A' },
      { ...KERTAS, product_name: 'B' },
      { ...KERTAS, product_name: 'C' },
    ])
    expect(rows.map((r) => r[3])).toEqual(['A', 'B', 'C'])
  })

  it('entries kosong -> tidak ada baris', () => {
    expect(buildLogRows([])).toEqual({ rows: [], skipped: [] })
  })
})
