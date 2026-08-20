import { describe, it, expect } from 'vitest'
import { MODES, DISPLAY, SUPPLIER, lokasiPilihan, lokasiAwal, siapLanjut, seringDipakai } from './mutasi'

const RACKS = ['Gudang Packaging', 'Gudang Bahan Kue', 'Gudang Ciherang', DISPLAY, 'Gudang Dapur Cherry']

describe('lokasiAwal', () => {
  it('mengunci tujuan ke Area Display untuk isi ulang', () => {
    expect(lokasiAwal(MODES.display)).toEqual({ from: '', to: DISPLAY })
  })

  it('mengunci asal ke Barang Datang untuk kiriman supplier', () => {
    expect(lokasiAwal(MODES.datang)).toEqual({ from: SUPPLIER, to: '' })
  })

  it('membiarkan kedua sisi kosong untuk pindah antar gudang', () => {
    expect(lokasiAwal(MODES.gudang)).toEqual({ from: '', to: '' })
  })
})

describe('lokasiPilihan', () => {
  it('menyembunyikan Area Display sebagai asal isi ulang', () => {
    expect(lokasiPilihan(MODES.display, RACKS)).not.toContain(DISPLAY)
  })

  it('mengizinkan barang datang langsung ke display', () => {
    expect(lokasiPilihan(MODES.datang, RACKS)).toContain(DISPLAY)
  })

  it('ikut daftar rak dari DB, bukan daftar tetap di kode', () => {
    expect(lokasiPilihan(MODES.datang, ['Gudang Baru'])).toEqual(['Gudang Baru'])
  })
})

describe('siapLanjut', () => {
  it('menolak asal dan tujuan yang sama', () => {
    expect(siapLanjut('Gudang Ciherang', 'Gudang Ciherang')).toBe(false)
  })

  it('menolak salah satu sisi yang masih kosong', () => {
    expect(siapLanjut('', DISPLAY)).toBe(false)
    expect(siapLanjut('Gudang Ciherang', '')).toBe(false)
  })

  it('menerima pasangan lokasi yang berbeda', () => {
    expect(siapLanjut('Gudang Ciherang', DISPLAY)).toBe(true)
  })
})

describe('seringDipakai', () => {
  const rows = [
    { product_name: 'Gula' }, { product_name: 'Gula' }, { product_name: 'Gula' },
    { product_name: 'Ceres' }, { product_name: 'Ceres' },
    { product_name: 'Blue Band' },
  ]

  it('mengurutkan dari yang paling sering', () => {
    expect(seringDipakai(rows).map((r) => r.product_name)).toEqual(['Gula', 'Ceres', 'Blue Band'])
  })

  it('memutus seri dengan nama supaya urutannya tidak berubah sendiri', () => {
    const seri = [{ product_name: 'Zeta' }, { product_name: 'Alfa' }]
    expect(seringDipakai(seri).map((r) => r.product_name)).toEqual(['Alfa', 'Zeta'])
  })

  it('memotong sesuai batas', () => {
    expect(seringDipakai(rows, 2)).toHaveLength(2)
  })

  it('aman saat riwayat masih kosong', () => {
    expect(seringDipakai([])).toEqual([])
    expect(seringDipakai(null)).toEqual([])
  })
})
