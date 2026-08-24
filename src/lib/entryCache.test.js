import { describe, it, expect } from 'vitest'
import { bacaEntriCache, hapusEntriCache, tulisEntriCache } from './entryCache'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

const RAK = 'Gudang Ciherang'

function baris(nama, extra = {}) {
  return { id: nama, product_name: nama, qty_total: 3, uploaded_at: null, ...extra }
}

describe('entryCache', () => {
  it('menyimpan lalu membaca kembali per rak + pemilik', () => {
    const store = storePalsu()
    tulisEntriCache(RAK, 'u1', { milik: [baris('Gula')], lain: [baris('Tepung')] }, store)
    expect(bacaEntriCache(RAK, 'u1', store)).toEqual({ milik: [baris('Gula')], lain: [baris('Tepung')] })
  })

  it('rak dan pemilik lain tidak saling menimpa', () => {
    const store = storePalsu()
    tulisEntriCache(RAK, 'u1', { milik: [baris('Gula')] }, store)
    tulisEntriCache(RAK, 'u2', { milik: [baris('Kopi')] }, store)
    tulisEntriCache('Area Display', 'u1', { milik: [baris('Teh')] }, store)
    expect(bacaEntriCache(RAK, 'u1', store).milik).toEqual([baris('Gula')])
    expect(bacaEntriCache(RAK, 'u2', store).milik).toEqual([baris('Kopi')])
    expect(bacaEntriCache('Area Display', 'u1', store).milik).toEqual([baris('Teh')])
  })

  it('entri yang sudah ter-upload tidak ikut disimpan', () => {
    const store = storePalsu()
    tulisEntriCache(RAK, 'u1', {
      milik: [baris('Gula'), baris('Kopi', { uploaded_at: '2026-08-24T01:00:00Z' })],
    }, store)
    expect(bacaEntriCache(RAK, 'u1', store).milik).toEqual([baris('Gula')])
  })

  it('rak yang belum pernah dibuka mengembalikan daftar kosong, bukan undefined', () => {
    expect(bacaEntriCache(RAK, 'u1', storePalsu())).toEqual({ milik: [], lain: [] })
  })

  it('isi rusak dianggap kosong, bukan melempar', () => {
    expect(bacaEntriCache(RAK, 'u1', storePalsu({ 'so-entries-v1': '{rusak' }))).toEqual({ milik: [], lain: [] })
    expect(bacaEntriCache(RAK, 'u1', storePalsu({ 'so-entries-v1': '[1,2]' }))).toEqual({ milik: [], lain: [] })
  })

  it('dipagari 500 baris supaya localStorage tidak jebol', () => {
    const store = storePalsu()
    const banyak = Array.from({ length: 700 }, (_, i) => baris(`P${i}`))
    tulisEntriCache(RAK, 'u1', { milik: banyak, lain: banyak }, store)
    const hasil = bacaEntriCache(RAK, 'u1', store)
    expect(hasil.milik).toHaveLength(500)
    expect(hasil.lain).toHaveLength(500)
  })

  it('kuota penuh dilaporkan false, tidak melempar', () => {
    const buntu = {
      getItem: () => null,
      setItem: () => { throw new Error('QuotaExceededError') },
      removeItem: () => {},
    }
    expect(tulisEntriCache(RAK, 'u1', { milik: [baris('Gula')] }, buntu)).toBe(false)
  })

  it('hapus mengosongkan seluruh cache', () => {
    const store = storePalsu()
    tulisEntriCache(RAK, 'u1', { milik: [baris('Gula')] }, store)
    hapusEntriCache(store)
    expect(bacaEntriCache(RAK, 'u1', store).milik).toEqual([])
  })
})
