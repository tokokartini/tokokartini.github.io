import { describe, it, expect } from 'vitest'
import { bacaCache, tulisCache, hapusCache, cacheMasihSah, PRODUCT_COLUMNS } from './productCache'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

const PRODUK = [
  { id: 1, sku: 'A-1', product_name: 'Gula Pasir', variant: 'Pcs', mult: 1, unit_order: 0, category: 'Bahan', brand: 'X', active: true },
  { id: 2, sku: 'A-2', product_name: 'Gula Pasir', variant: 'Krtn (50 Pcs)', mult: 50, unit_order: 1, category: 'Bahan', brand: 'X', active: true },
]

describe('tulis/baca cache', () => {
  it('bolak-balik utuh', () => {
    const s = storePalsu()
    expect(tulisCache('2026-08-10T20:00:00Z', PRODUK, s)).toBe(true)
    const c = bacaCache(s)
    expect(c.stamp).toBe('2026-08-10T20:00:00Z')
    expect(c.count).toBe(2)
    expect(c.products).toHaveLength(2)
  })

  it('membuang kolom yang tidak dipakai supaya cache kecil', () => {
    const s = storePalsu()
    tulisCache('t', PRODUK, s)
    const p = bacaCache(s).products[0]
    expect(Object.keys(p).sort()).toEqual(
      ['brand', 'category', 'mult', 'product_name', 'sku', 'unit_order', 'variant'],
    )
    expect(p.id).toBeUndefined()
    expect(p.active).toBeUndefined()
  })

  it('kolom yang diminta ke server sama dengan yang disimpan', () => {
    expect(PRODUCT_COLUMNS).toBe('sku, product_name, variant, mult, unit_order, category, brand')
  })

  it('cache kosong dianggap tidak ada', () => {
    const s = storePalsu()
    tulisCache('t', [], s)
    expect(bacaCache(s)).toBeNull()
  })

  it('JSON rusak tidak melempar error', () => {
    const s = storePalsu({ 'so-products-v1': '{bukan json' })
    expect(bacaCache(s)).toBeNull()
  })

  it('localStorage diblokir tidak melempar error', () => {
    const mati = {
      getItem: () => { throw new Error('blocked') },
      setItem: () => { throw new Error('blocked') },
      removeItem: () => { throw new Error('blocked') },
    }
    expect(bacaCache(mati)).toBeNull()
    expect(tulisCache('t', PRODUK, mati)).toBe(false)
    expect(() => hapusCache(mati)).not.toThrow()
  })

  it('hapus membersihkan cache', () => {
    const s = storePalsu()
    tulisCache('t', PRODUK, s)
    hapusCache(s)
    expect(bacaCache(s)).toBeNull()
  })
})

describe('cacheMasihSah', () => {
  const cache = { stamp: 'T1', count: 2, products: PRODUK }

  it('sah kalau penanda sync dan jumlah produk sama', () => {
    expect(cacheMasihSah(cache, { stamp: 'T1', count: 2 })).toBe(true)
  })

  it('basi kalau sync baru jalan', () => {
    expect(cacheMasihSah(cache, { stamp: 'T2', count: 2 })).toBe(false)
  })

  // Produk bisa diubah langsung di tabel tanpa lewat sync (mis. perbaikan manual).
  // Penanda tidak bergerak, jadi jumlah produk yang jadi jaring pengaman.
  it('basi kalau jumlah produk berubah walau penanda sama', () => {
    expect(cacheMasihSah(cache, { stamp: 'T1', count: 3 })).toBe(false)
  })

  it('tidak percaya cache kalau salah satu penanda hilang', () => {
    expect(cacheMasihSah(cache, { stamp: null, count: 2 })).toBe(false)
    expect(cacheMasihSah({ ...cache, stamp: null }, { stamp: 'T1', count: 2 })).toBe(false)
  })

  it('tidak percaya cache kalau jumlah dari server gagal terbaca', () => {
    expect(cacheMasihSah(cache, { stamp: 'T1', count: null })).toBe(false)
  })

  it('tanpa cache atau tanpa data server: tidak sah', () => {
    expect(cacheMasihSah(null, { stamp: 'T1', count: 2 })).toBe(false)
    expect(cacheMasihSah(cache, null)).toBe(false)
  })
})
