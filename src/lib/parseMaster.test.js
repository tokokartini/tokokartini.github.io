import { describe, it, expect } from 'vitest'
import { parseMaster, parseIsi } from './parseMaster'

const kosong = () => Array(32).fill('')
function baris({ kategori = 'Bahan', merek = 'X', nama = 'Produk', slots = [] }) {
  const r = kosong()
  r[0] = kategori; r[2] = merek; r[3] = nama
  const kolom = [[28, 6, null], [29, 8, 7], [30, 10, 9], [31, 12, 11]]
  slots.forEach(([sku, satuan, isi], i) => {
    const [skuI, satI, isiI] = kolom[i]
    r[skuI] = sku; r[satI] = satuan
    if (isiI !== null && isi !== undefined) r[isiI] = isi
  })
  return r
}
const sheet = (...rows) => [kosong(), kosong(), ...rows]

describe('parseIsi', () => {
  it('buang pemisah ribuan, koma jadi desimal', () => {
    expect(parseIsi('1.200')).toBe(1200)
    expect(parseIsi('2,5')).toBe(2.5)
  })
  it('kosong dan strip jadi null', () => {
    expect(parseIsi('')).toBeNull()
    expect(parseIsi('-')).toBeNull()
    expect(parseIsi('abc')).toBeNull()
  })
})

describe('parseMaster', () => {
  it('hitung mult dari isi terbesar', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'Kresek', slots: [['K-G', 'Bal'], ['K-3', 'Pack', '20']] }),
    ))
    expect(products.map((p) => [p.sku, p.mult, p.unit_order]))
      .toEqual([['K-G', 20, 0], ['K-3', 1, 1]])
  })

  it('satuan kosong dilewati dan dihitung', () => {
    const { products, skipped } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['A-G', ''], ['A-3', 'Pack', '5']] }),
    ))
    expect(skipped).toBe(1)
    expect(products.map((p) => p.sku)).toEqual(['A-3'])
  })

  it('sku duplikat dihitung sekali', () => {
    const { products, dupes } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['SAMA', 'Bal']] }),
      baris({ nama: 'B', slots: [['SAMA', 'Pack', '5']] }),
    ))
    expect(dupes).toBe(1)
    expect(products).toHaveLength(1)
    expect(products[0].product_name).toBe('A')
  })

  it('isi rusak bikin semua mult jadi 1', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'A', slots: [['A-G', 'Bal'], ['A-3', 'Pack', '-']] }),
    ))
    expect(products.map((p) => p.mult)).toEqual([1, 1])
  })

  it('baris pemisah === dan baris tanpa nama diabaikan', () => {
    const { products } = parseMaster(sheet(
      baris({ kategori: '=== BAHAN ===', nama: 'Jangan', slots: [['X-1', 'Pcs']] }),
      baris({ nama: '', slots: [['Y-1', 'Pcs']] }),
    ))
    expect(products).toHaveLength(0)
  })

  it('kategori dan merek ikut terbawa', () => {
    const { products } = parseMaster(sheet(
      baris({ kategori: 'Mika', merek: 'DP', nama: 'Mika 7C', slots: [['M-1', 'Pack']] }),
    ))
    expect(products[0]).toMatchObject({ category: 'Mika', brand: 'DP', active: true })
  })
})
