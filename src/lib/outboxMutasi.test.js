import { describe, it, expect } from 'vitest'
import {
  antreMutasi,
  bacaOutboxMutasi,
  buangOutboxMutasi,
  outboxSuratJalan,
  tulisOutboxMutasi,
} from './outboxMutasi'
import { bacaOutbox, antre as antreSO } from './outbox'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

function baris(nama, { from = 'Gudang Ciherang', to = 'Area Display', uid = 'u1', qty = 5 } = {}) {
  return {
    from_loc: from,
    to_loc: to,
    user_id: uid,
    jenis: 'Isi Ulang',
    product_name: nama,
    server_id: null,
    units: [{ sku: 'A-1', variant: 'Pcs', mult: 1, qty }],
    qty_total: qty,
    nota: '',
    username: 'rian',
    updated_at: '2026-08-24T01:00:00.000Z',
  }
}

describe('antrian surat jalan', () => {
  it('menyimpan lalu membaca kembali', () => {
    const store = storePalsu()
    const { item } = antreMutasi(baris('Gula'), store)
    expect(item.id).toMatch(/^lokal:/)
    expect(bacaOutboxMutasi(store)).toHaveLength(1)
  })

  it('produk sama di surat jalan sama MENIMPA, bukan menumpuk', () => {
    const store = storePalsu()
    antreMutasi(baris('Gula', { qty: 5 }), store)
    antreMutasi(baris('Gula', { qty: 9 }), store)
    const list = bacaOutboxMutasi(store)
    expect(list).toHaveLength(1)
    expect(list[0].qty_total).toBe(9)
  })

  it('produk sama di surat jalan BERBEDA tetap dua baris', () => {
    const store = storePalsu()
    antreMutasi(baris('Gula', { to: 'Area Display' }), store)
    antreMutasi(baris('Gula', { to: 'Gudang Dapur Cherry' }), store)
    expect(bacaOutboxMutasi(store)).toHaveLength(2)
  })

  it('asal berbeda juga dianggap surat jalan berbeda', () => {
    const store = storePalsu()
    antreMutasi(baris('Gula', { from: 'Gudang Ciherang' }), store)
    antreMutasi(baris('Gula', { from: 'Gudang Bahan Kue' }), store)
    expect(bacaOutboxMutasi(store)).toHaveLength(2)
  })

  it('orang lain tidak saling menimpa', () => {
    const store = storePalsu()
    antreMutasi(baris('Gula', { uid: 'u1' }), store)
    antreMutasi(baris('Gula', { uid: 'u2' }), store)
    expect(bacaOutboxMutasi(store)).toHaveLength(2)
  })

  it('outboxSuratJalan menyaring per pasangan lokasi + pemilik', () => {
    const list = [
      baris('Gula', { to: 'Area Display', uid: 'u1' }),
      baris('Kopi', { to: 'Gudang Dapur Cherry', uid: 'u1' }),
      baris('Teh', { to: 'Area Display', uid: 'u2' }),
    ]
    const hasil = outboxSuratJalan(list, 'Gudang Ciherang', 'Area Display', 'u1')
    expect(hasil.map((h) => h.product_name)).toEqual(['Gula'])
  })

  it('buang menghapus satu baris saja', () => {
    const store = storePalsu()
    const { item } = antreMutasi(baris('Gula'), store)
    antreMutasi(baris('Kopi'), store)
    buangOutboxMutasi(item.id, store)
    expect(bacaOutboxMutasi(store).map((i) => i.product_name)).toEqual(['Kopi'])
  })

  it('isi rusak dianggap kosong, bukan melempar', () => {
    expect(bacaOutboxMutasi(storePalsu({ 'so-outbox-mutasi-v1': '{rusak' }))).toEqual([])
  })

  it('kuota penuh dilaporkan, tidak ditelan diam-diam', () => {
    const buntu = {
      getItem: () => null,
      setItem: () => { throw new Error('QuotaExceededError') },
      removeItem: () => {},
    }
    expect(tulisOutboxMutasi([baris('Gula')], buntu)).toBe(false)
    expect(antreMutasi(baris('Gula'), buntu).tersimpan).toBe(false)
  })

  it('TIDAK berbagi slot dengan antrian stock opname', () => {
    const store = storePalsu()
    antreMutasi(baris('Gula'), store)
    antreSO({ rack: 'Gudang Ciherang', user_id: 'u1', product_name: 'Gula', qty_total: 3 }, store)
    expect(bacaOutboxMutasi(store)).toHaveLength(1)
    expect(bacaOutbox(store)).toHaveLength(1)
    expect([...store._map.keys()].sort()).toEqual(['so-outbox-mutasi-v1', 'so-outbox-v1'])
  })
})
