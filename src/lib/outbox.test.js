import { describe, it, expect } from 'vitest'
import {
  AWALAN_LOKAL,
  adalahLokal,
  antre,
  bacaOutbox,
  buangOutbox,
  denganBatasWaktu,
  gagalJaringan,
  idLokal,
  outboxRak,
  tulisOutbox,
} from './outbox'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

function entri(nama, rack = 'Gudang Dapur Cherry', uid = 'u1', qty = 5) {
  return {
    rack,
    user_id: uid,
    product_name: nama,
    server_id: null,
    units: [{ sku: 'A-1', variant: 'Pcs', mult: 1, qty }],
    qty_total: qty,
    expired_date: null,
    username: 'rian',
    updated_at: '2026-08-22T01:00:00.000Z',
  }
}

describe('antre', () => {
  it('menyimpan entri dan memberi id lokal', () => {
    const s = storePalsu()
    const { item, tersimpan } = antre(entri('Gula Pasir'), s)
    expect(tersimpan).toBe(true)
    expect(item.id.startsWith(AWALAN_LOKAL)).toBe(true)
    expect(bacaOutbox(s)).toHaveLength(1)
  })

  it('menimpa entri produk yang sama di rak yang sama — bukan menumpuk', () => {
    const s = storePalsu()
    antre(entri('Gula Pasir', 'Gudang Dapur Cherry', 'u1', 5), s)
    antre(entri('Gula Pasir', 'Gudang Dapur Cherry', 'u1', 8), s)
    const list = bacaOutbox(s)
    expect(list).toHaveLength(1)
    expect(list[0].qty_total).toBe(8)
  })

  it('produk sama di rak berbeda tetap dua baris', () => {
    const s = storePalsu()
    antre(entri('Gula Pasir', 'Gudang Ciherang'), s)
    antre(entri('Gula Pasir', 'Area Display'), s)
    expect(bacaOutbox(s)).toHaveLength(2)
  })

  it('produk sama milik orang berbeda tetap dua baris', () => {
    const s = storePalsu()
    antre(entri('Gula Pasir', 'Gudang Ciherang', 'u1'), s)
    antre(entri('Gula Pasir', 'Gudang Ciherang', 'u2'), s)
    expect(bacaOutbox(s)).toHaveLength(2)
  })

  it('mempertahankan id saat entri antrian diedit lagi', () => {
    const s = storePalsu()
    const { item } = antre(entri('Gula Pasir'), s)
    const lagi = antre({ ...entri('Gula Pasir', 'Gudang Dapur Cherry', 'u1', 12), id: item.id }, s)
    expect(lagi.item.id).toBe(item.id)
    expect(bacaOutbox(s)).toHaveLength(1)
    expect(bacaOutbox(s)[0].qty_total).toBe(12)
  })

  it('melaporkan gagal kalau simpanan penuh — bukan diam-diam hilang', () => {
    const s = storePalsu()
    s.setItem = () => { throw new Error('QuotaExceededError') }
    expect(antre(entri('Gula Pasir'), s).tersimpan).toBe(false)
  })
})

describe('baca outbox', () => {
  it('kosong kalau belum ada apa-apa', () => {
    expect(bacaOutbox(storePalsu())).toEqual([])
  })

  it('kosong kalau JSON rusak', () => {
    expect(bacaOutbox(storePalsu({ 'so-outbox-v1': '{rusak' }))).toEqual([])
  })

  it('kosong kalau localStorage diblokir', () => {
    const s = storePalsu()
    s.getItem = () => { throw new Error('ditolak') }
    expect(bacaOutbox(s)).toEqual([])
  })

  it('membuang baris tanpa id atau nama produk', () => {
    const s = storePalsu({ 'so-outbox-v1': JSON.stringify([{ id: 'lokal:1' }, { product_name: 'X' }, null]) })
    expect(bacaOutbox(s)).toEqual([])
  })

  it('kosong kalau isinya bukan larik', () => {
    expect(bacaOutbox(storePalsu({ 'so-outbox-v1': '{"a":1}' }))).toEqual([])
  })
})

describe('buang & saring', () => {
  it('buang satu id, sisanya utuh', () => {
    const s = storePalsu()
    const a = antre(entri('Gula Pasir'), s).item
    antre(entri('Tepung'), s)
    buangOutbox(a.id, s)
    const list = bacaOutbox(s)
    expect(list).toHaveLength(1)
    expect(list[0].product_name).toBe('Tepung')
  })

  it('outboxRak menyaring per rak dan per pemilik', () => {
    const list = [
      entri('A', 'Gudang Ciherang', 'u1'),
      entri('B', 'Area Display', 'u1'),
      entri('C', 'Gudang Ciherang', 'u2'),
    ]
    expect(outboxRak(list, 'Gudang Ciherang', 'u1').map((e) => e.product_name)).toEqual(['A'])
  })
})

describe('id lokal', () => {
  it('dikenali adalahLokal, id server tidak', () => {
    expect(adalahLokal(idLokal())).toBe(true)
    expect(adalahLokal('3f6d1e88-0000-4000-8000-000000000000')).toBe(false)
    expect(adalahLokal(undefined)).toBe(false)
    expect(adalahLokal(12)).toBe(false)
  })

  it('jalan tanpa crypto.randomUUID', () => {
    expect(adalahLokal(idLokal({}))).toBe(true)
  })
})

describe('gagalJaringan', () => {
  const online = { onLine: true }

  it('true untuk kegagalan fetch', () => {
    expect(gagalJaringan(new TypeError('Failed to fetch'), online)).toBe(true)
    expect(gagalJaringan(new Error('NetworkError when attempting to fetch resource'), online)).toBe(true)
    expect(gagalJaringan(new Error('Load failed'), online)).toBe(true)
  })

  it('true kalau browser tahu dirinya offline, apa pun errornya', () => {
    expect(gagalJaringan(null, { onLine: false })).toBe(true)
    expect(gagalJaringan({ code: '23505' }, { onLine: false })).toBe(true)
  })

  it('false untuk penolakan server — punya code, jangan diantre', () => {
    expect(gagalJaringan({ code: '23505', message: 'duplicate key' }, online)).toBe(false)
    expect(gagalJaringan({ code: '42501', message: 'row-level security' }, online)).toBe(false)
  })

  it('false untuk error biasa tanpa ciri jaringan', () => {
    expect(gagalJaringan(new Error('kolom qty tidak ada'), online)).toBe(false)
    expect(gagalJaringan(null, online)).toBe(false)
  })

  it('tulisOutbox mengembalikan false saat kuota penuh', () => {
    const s = storePalsu()
    s.setItem = () => { throw new Error('penuh') }
    expect(tulisOutbox([entri('X')], s)).toBe(false)
  })
})

describe('denganBatasWaktu', () => {
  it('meneruskan hasil yang datang tepat waktu', async () => {
    await expect(denganBatasWaktu(Promise.resolve({ data: 1 }), 50)).resolves.toEqual({ data: 1 })
  })

  it('menyerah kalau server menggantung, dan itu terbaca sebagai gagal jaringan', async () => {
    const err = await denganBatasWaktu(new Promise(() => {}), 10).catch((e) => e)
    expect(err.message).toMatch(/timeout/)
    expect(gagalJaringan(err, { onLine: true })).toBe(true)
  })

  it('error asli tetap diteruskan apa adanya', async () => {
    const err = await denganBatasWaktu(Promise.reject(new Error('ditolak')), 50).catch((e) => e)
    expect(err.message).toBe('ditolak')
  })
})
