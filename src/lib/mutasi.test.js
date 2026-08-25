import { describe, it, expect } from 'vitest'
import {
  MODES, MODE_KEYS, DISPLAY, SUPPLIER, BUANG, SEBAB,
  modeOf, lokasiPilihan, lokasiAwal, siapLanjut, seringDipakai, sebabSah, sebabUntuk,
} from './mutasi'

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

describe('barang rusak', () => {
  it('jenis rusak mengunci tujuan ke lokasi maya, asalnya bebas termasuk display', () => {
    const m = modeOf('rusak')
    expect(m.jenis).toBe('Rusak')
    expect(lokasiAwal(m)).toEqual({ from: '', to: BUANG })
    // Display harus boleh jadi asal -- barang pajangan juga bisa rusak.
    expect(lokasiPilihan(m, ['Gudang Ciherang', DISPLAY])).toEqual(['Gudang Ciherang', DISPLAY])
  })

  it('lokasi maya tidak pernah muncul sebagai pilihan lokasi', () => {
    // racks datang dari tabel racks, dan BUANG bukan baris di sana. Uji ini
    // menjaga andai suatu hari ada yang menambahkannya ke DB.
    for (const k of MODE_KEYS) {
      expect(lokasiPilihan(modeOf(k), ['Gudang Ciherang', DISPLAY])).not.toContain(BUANG)
    }
  })

  it('sebab wajib untuk rusak, dan harus dari daftar', () => {
    const m = modeOf('rusak')
    expect(sebabSah(m, 'Kadaluarsa')).toBe(true)
    expect(sebabSah(m, '')).toBe(false)
    expect(sebabSah(m, 'alasan karangan')).toBe(false)
  })

  it('sebab tidak boleh ikut jenis lain', () => {
    for (const k of ['display', 'datang', 'gudang']) {
      const m = modeOf(k)
      expect(sebabSah(m, '')).toBe(true)
      expect(sebabSah(m, 'Kadaluarsa')).toBe(false)
      // Sebab yang tertinggal saat petugas pindah jenis dibuang, bukan terbawa.
      expect(sebabUntuk(m, 'Kadaluarsa')).toBe('')
    }
    expect(sebabUntuk(modeOf('rusak'), 'Kadaluarsa')).toBe('Kadaluarsa')
  })

  it('Hilang sengaja bukan pilihan sebab', () => {
    // Barang hilang ketahuan lewat selisih SO, bukan dicatat manual. Kalau
    // disediakan, dipakai untuk menutupi yang sebenarnya rusak.
    expect(SEBAB.some((s) => /hilang/i.test(s))).toBe(false)
  })
})
