// Menguji penyusun baris tab Mutasi: 11 kolom, urutannya dikunci karena tab Rekap
// Mutasi menunjuk kolom ini lewat nomor Col di string QUERY.
import { describe, it, expect } from 'vitest'
import { baseUnitOf, buildMutasiRows, rincianText, wib } from './rows.ts'

const GULA = {
  updated_at: '2026-08-20T02:14:00.000+00:00',
  username: 'naruto',
  jenis: 'Isi Ulang',
  from_loc: 'Gudang Bahan Kue',
  to_loc: 'Area Display',
  nota: '',
  product_name: 'Gula Pasir Gulaku 1kg',
  units: [
    { sku: 'GLK-KRT', variant: 'Krtn (20 Pack)', mult: 20, qty: 1 },
    { sku: 'GLK-PCK', variant: 'Pack', mult: 1, qty: 5 },
  ],
  qty_total: 25,
}

const DATANG = {
  ...GULA,
  jenis: 'Datang',
  from_loc: 'Barang Datang',
  to_loc: 'Gudang Bahan Kue',
  nota: 'PT Sinar Jaya 4471',
  units: [{ sku: 'GLK-KRT', variant: 'Krtn (20 Pack)', mult: 20, qty: 10 }],
  qty_total: 200,
}

describe('wib', () => {
  it('geser +7 jam, format YYYY-MM-DD HH:MM:SS', () => {
    expect(wib('2026-08-20T02:14:00.000+00:00')).toBe('2026-08-20 09:14:00')
  })

  it('lewat tengah malam UTC tetap benar', () => {
    expect(wib('2026-08-19T20:00:00.000+00:00')).toBe('2026-08-20 03:00:00')
  })
})

describe('baseUnitOf', () => {
  it('pilih satuan dengan mult 1', () => {
    expect(baseUnitOf(GULA.units)?.sku).toBe('GLK-PCK')
  })

  it('tanpa mult 1, pilih mult terkecil', () => {
    expect(baseUnitOf(DATANG.units)?.sku).toBe('GLK-KRT')
  })

  it('units kosong / null', () => {
    expect(baseUnitOf([])).toBeNull()
    expect(baseUnitOf(null)).toBeNull()
  })
})

describe('rincianText', () => {
  it('satuan besar dulu, dipisah +', () => {
    expect(rincianText(GULA.units)).toBe('1 Krtn (20 Pack) + 5 Pack')
  })

  it('satuan berisi 0 tidak ditulis', () => {
    const units = [
      { sku: 'A', variant: 'Krtn', mult: 20, qty: 0 },
      { sku: 'B', variant: 'Pack', mult: 1, qty: 7 },
    ]
    expect(rincianText(units)).toBe('7 Pack')
  })

  it('satuan negatif tetap ditulis supaya Rincian nyambung dengan Qty', () => {
    const units = [
      { sku: 'A', variant: 'Krtn', mult: 20, qty: 2 },
      { sku: 'B', variant: 'Pack', mult: 1, qty: -3 },
    ]
    expect(rincianText(units)).toBe('2 Krtn + -3 Pack')
  })
})

describe('buildMutasiRows', () => {
  it('11 kolom, urutan Waktu Staff Jenis Dari Ke Produk Rincian Qty Satuan SKU Nota', () => {
    const { rows } = buildMutasiRows([GULA])
    expect(rows).toHaveLength(1)
    expect(rows[0]).toEqual([
      '2026-08-20 09:14:00',
      'naruto',
      'Isi Ulang',
      'Gudang Bahan Kue',
      'Area Display',
      'Gula Pasir Gulaku 1kg',
      '1 Krtn (20 Pack) + 5 Pack',
      25,
      'Pack',
      'GLK-PCK',
      '',
    ])
  })

  it('barang datang membawa nota dan satuan terkecil yang tersedia', () => {
    const { rows } = buildMutasiRows([DATANG])
    expect(rows[0][2]).toBe('Datang')
    expect(rows[0][3]).toBe('Barang Datang')
    expect(rows[0][8]).toBe('Krtn (20 Pack)')
    expect(rows[0][10]).toBe('PT Sinar Jaya 4471')
  })

  it('jenis diambil dari DB apa adanya, tidak disimpulkan dari nama lokasi', () => {
    const aneh = { ...GULA, jenis: 'Pindah', from_loc: 'Gudang Ciherang', to_loc: 'Gudang Packaging' }
    expect(buildMutasiRows([aneh]).rows[0][2]).toBe('Pindah')
  })

  it('nota null jadi teks kosong, bukan "null"', () => {
    const { rows } = buildMutasiRows([{ ...GULA, nota: null }])
    expect(rows[0][10]).toBe('')
  })

  it('baris tanpa satuan dilewati, sisanya tetap masuk', () => {
    const rusak = { ...GULA, product_name: 'Tanpa Satuan', units: null }
    const { rows, skipped } = buildMutasiRows([rusak, GULA])
    expect(rows).toHaveLength(1)
    expect(rows[0][5]).toBe('Gula Pasir Gulaku 1kg')
    expect(skipped).toEqual(['Tanpa Satuan'])
  })

  it('qty_total null jadi 0, bukan NaN', () => {
    const { rows } = buildMutasiRows([{ ...GULA, qty_total: null }])
    expect(rows[0][7]).toBe(0)
  })
})
