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
  it('titik-saja jadi null, bukan 0 (beda dari Number(""))', () => {
    expect(parseIsi('.')).toBeNull()
    expect(parseIsi('..')).toBeNull()
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

  it('isi 0 memaksa mult unit itu sendiri jadi 1 lewat cabang `!u.isi`, walau broken tetap false', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'C', slots: [['C-G', 'Bal'], ['C-1', 'Dus', '0'], ['C-2', 'Pack', '10']] }),
    ))
    // broken tetap false (0 !== null, bukan null) -- tapi C-1 sendiri kena `!u.isi`
    // (0 falsy) -> mult dipaksa 1, terlepas dari broken.
    // Catatan: ini TIDAK memin `isis.filter(Boolean)` (baris di parseMaster.js yang
    // membuang isi 0 dari base). filter(Boolean) provably tidak berpengaruh ke
    // output di sini -- lihat komentarnya di parseMaster.js -- jadi bukan sesuatu
    // yang bisa/perlu dipin oleh test manapun.
    expect(products.map((p) => [p.sku, p.mult])).toEqual([
      ['C-G', 10],
      ['C-1', 1],
      ['C-2', 1],
    ])
  })

  it('hanya baca dari index 2 -- dua baris pertama dibuang meski berisi produk valid', () => {
    const asli = [
      baris({ nama: 'Baris0', slots: [['B0-1', 'Pcs']] }),
      baris({ nama: 'Baris1', slots: [['B1-1', 'Pcs']] }),
      baris({ nama: 'Baris2', slots: [['B2-1', 'Pcs']] }),
    ]
    const { products } = parseMaster(asli)
    expect(products.map((p) => p.sku)).toEqual(['B2-1'])
  })

  it('semua 4 slot satuan (termasuk kolom 30/10/9 dan 31/12/11) terbaca dengan urutan benar', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'Multi', slots: [
        ['S0', 'Bal'],
        ['S1', 'Pack', '10'],
        ['S2', 'Dus', '50'],
        ['S3', 'Pcs', '100'],
      ] }),
    ))
    expect(products.map((p) => [p.sku, p.variant, p.unit_order]))
      .toEqual([
        ['S0', 'Bal', 0],
        ['S1', 'Pack', 1],
        ['S2', 'Dus', 2],
        ['S3', 'Pcs', 3],
      ])
  })

  it('baris pendek dari Sheets API mentah (bukan gspread, yang selalu padding 32) tetap terparse benar', () => {
    const pendek = []
    pendek[0] = 'Bahan'
    pendek[2] = 'X'
    pendek[3] = 'Ringkas'
    pendek[6] = 'Bal'
    pendek[28] = 'R-1'
    expect(pendek.length).toBeLessThan(32)
    const { products } = parseMaster([kosong(), kosong(), pendek])
    expect(products).toHaveLength(1)
    expect(products[0]).toMatchObject({
      sku: 'R-1', variant: 'Bal', category: 'Bahan', brand: 'X', product_name: 'Ringkas',
    })
    // Catatan: ini memverifikasi baris pendek (lebar 1, seperti yang benar-benar
    // dikembalikan Sheets API untuk baris data pertama) tetap terparse benar. Ini
    // TIDAK memin baris `while (row.length < 32) row.push('')` itu sendiri -- di JS
    // setiap akses field sudah lewat `row[i] ?? ''` yang aman untuk index di luar
    // batas, jadi loop itu dead-for-behavior di sini (lihat komentarnya di
    // parseMaster.js). Loop-nya tetap dipertahankan supaya persis mencerminkan
    // scripts/sync_products.py, tempat padding itu justru load-bearing.
  })

  it('mult dibulatkan 4 desimal (20/3 = 6.6667)', () => {
    const { products } = parseMaster(sheet(
      baris({ nama: 'B', slots: [['B-G', 'Bal'], ['B-1', 'Dus', '20'], ['B-2', 'Pack', '3']] }),
    ))
    expect(products.find((p) => p.sku === 'B-2').mult).toBe(6.6667)
  })
})
