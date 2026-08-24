import { describe, it, expect } from 'vitest'
import { bacaMutasiCache, hapusMutasiCache, tulisMutasiCache } from './movementCache'
import { bacaEntriCache, tulisEntriCache } from './entryCache'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

const A = 'Gudang Ciherang'
const B = 'Area Display'
const baris = (nama, extra = {}) => ({ id: nama, product_name: nama, qty_total: 4, uploaded_at: null, ...extra })

describe('movementCache', () => {
  it('menyimpan lalu membaca per pasangan lokasi + pemilik', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula')], store)
    expect(bacaMutasiCache(A, B, 'u1', store)).toEqual([baris('Gula')])
  })

  it('surat jalan ke tujuan berbeda tidak tercampur', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula')], store)
    tulisMutasiCache(A, 'Gudang Dapur Cherry', 'u1', [baris('Kopi')], store)
    expect(bacaMutasiCache(A, B, 'u1', store).map((r) => r.product_name)).toEqual(['Gula'])
    expect(bacaMutasiCache(A, 'Gudang Dapur Cherry', 'u1', store).map((r) => r.product_name)).toEqual(['Kopi'])
  })

  it('pemilik berbeda tidak tercampur', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula')], store)
    tulisMutasiCache(A, B, 'u2', [baris('Kopi')], store)
    expect(bacaMutasiCache(A, B, 'u1', store).map((r) => r.product_name)).toEqual(['Gula'])
  })

  it('baris yang sudah terkirim tidak ikut disimpan', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula'), baris('Kopi', { uploaded_at: '2026-08-24T00:00:00Z' })], store)
    expect(bacaMutasiCache(A, B, 'u1', store).map((r) => r.product_name)).toEqual(['Gula'])
  })

  it('belum pernah dibuka mengembalikan daftar kosong', () => {
    expect(bacaMutasiCache(A, B, 'u1', storePalsu())).toEqual([])
  })

  it('isi rusak dianggap kosong', () => {
    expect(bacaMutasiCache(A, B, 'u1', storePalsu({ 'so-movements-v1': '[1,2]' }))).toEqual([])
  })

  it('dipagari 500 baris', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', Array.from({ length: 700 }, (_, i) => baris(`P${i}`)), store)
    expect(bacaMutasiCache(A, B, 'u1', store)).toHaveLength(500)
  })

  it('TIDAK berbagi slot dengan cache entri stock opname', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula')], store)
    tulisEntriCache(A, 'u1', { milik: [baris('Kopi')] }, store)
    expect(bacaMutasiCache(A, B, 'u1', store)).toHaveLength(1)
    expect(bacaEntriCache(A, 'u1', store).milik).toHaveLength(1)
    expect([...store._map.keys()].sort()).toEqual(['so-entries-v1', 'so-movements-v1'])
  })

  it('hapus mengosongkan cache', () => {
    const store = storePalsu()
    tulisMutasiCache(A, B, 'u1', [baris('Gula')], store)
    hapusMutasiCache(store)
    expect(bacaMutasiCache(A, B, 'u1', store)).toEqual([])
  })
})
