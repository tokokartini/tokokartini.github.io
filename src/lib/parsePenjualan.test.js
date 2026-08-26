import { describe, it, expect } from 'vitest'
import { zipSync, strToU8 } from 'fflate'
import {
  bacaXlsx, keBaris, parsePenjualan, serialKeTanggal, nomorKolom, KOLOM,
} from './parsePenjualan.js'

// Bikin .xlsx tiruan supaya test tidak butuh berkas export sungguhan -- yang itu
// penuh nama pelanggan, nomor HP, dan email karyawan, jadi tidak boleh ikut repo.
// Bentuk yang ditiru sama persis dengan keluaran POS: teks lewat sharedStrings,
// angka ditulis langsung.
function bikinXlsx(tabel) {
  const kamus = []
  const nomor = new Map()
  const idTeks = (s) => {
    if (!nomor.has(s)) { nomor.set(s, kamus.length); kamus.push(s) }
    return nomor.get(s)
  }
  const huruf = (i) => {
    let s = ''
    for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) {
      s = String.fromCharCode(65 + ((n - 1) % 26)) + s
    }
    return s
  }
  const barisXml = tabel.map((baris, r) => {
    const sel = baris.map((nilai, c) => {
      if (nilai === null || nilai === undefined || nilai === '') return ''
      const ref = `${huruf(c)}${r + 1}`
      if (typeof nilai === 'number') return `<c r="${ref}"><v>${nilai}</v></c>`
      if (typeof nilai === 'object' && nilai.inline) {
        return `<c r="${ref}" t="inlineStr"><is><t>${nilai.inline}</t></is></c>`
      }
      return `<c r="${ref}" t="s"><v>${idTeks(String(nilai))}</v></c>`
    }).join('')
    return `<row r="${r + 1}">${sel}</row>`
  }).join('')

  const si = kamus.map((s) => {
    const aman = s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return `<si><t>${aman}</t></si>`
  }).join('')

  return zipSync({
    'xl/sharedStrings.xml':
      strToU8(`<?xml version="1.0"?><sst count="${kamus.length}">${si}</sst>`),
    'xl/worksheets/sheet1.xml':
      strToU8(`<?xml version="1.0"?><worksheet><sheetData>${barisXml}</sheetData></worksheet>`),
  })
}

const JUDUL = [
  'order no', 'order date', 'order time', 'return date', 'brand', 'item group',
  'item name', 'item sku', 'qty', 'qty_with_converter', 'amount', 'profit',
  'paid', 'payment type', 'customer name', 'sales email',
]
// Tanggal 2026-08-17 dalam penanggalan Excel.
const SERIAL_17_AGU = 46251

function baris(ubah = {}) {
  const b = {
    'order no': 'INV-1', 'order date': SERIAL_17_AGU, 'order time': '07:00',
    'return date': '', brand: 'DM', 'item group': 'Packaging',
    'item name': 'Thinwall DM 200RB - Trs', 'item sku': 'PKG-0118-3',
    qty: 2, qty_with_converter: 2, amount: 21000, profit: 3000,
    paid: '1', 'payment type': 'CASH', 'customer name': '',
    'sales email': 'kasir@toko.test', ...ubah,
  }
  return JUDUL.map((j) => b[j])
}

describe('penanggalan Excel', () => {
  it('mengubah nomor hari jadi tanggal', () => {
    expect(serialKeTanggal(SERIAL_17_AGU)).toBe('2026-08-17')
    expect(serialKeTanggal(45658)).toBe('2025-01-01')
  })
})

describe('nomorKolom', () => {
  it('membaca alamat sel, termasuk dua huruf', () => {
    expect(nomorKolom('A1')).toBe(0)
    expect(nomorKolom('Z9')).toBe(25)
    expect(nomorKolom('AA1')).toBe(26)
    expect(nomorKolom('BQ2761')).toBe(68)
  })
})

describe('bacaXlsx', () => {
  it('membaca teks, angka, dan teks inline', () => {
    const t = bacaXlsx(bikinXlsx([['a', 1.5, { inline: 'c' }]]))
    expect(t[0]).toEqual(['a', '1.5', 'c'])
  })

  it('sel kosong tetap menggeser kolom', () => {
    // Di xlsx sel kosong memang tidak ditulis. Kalau alamatnya diabaikan,
    // 'z' akan terbaca di kolom 1 dan SELURUH kolom sesudahnya melenceng.
    const t = bacaXlsx(bikinXlsx([['a', '', '', 'z']]))
    expect(t[0]).toEqual(['a', '', '', 'z'])
    expect(t[0][3]).toBe('z')
  })

  it('teks yang mengandung & dan < utuh', () => {
    const t = bacaXlsx(bikinXlsx([['Roti & Kue < 500gr']]))
    expect(t[0][0]).toBe('Roti & Kue < 500gr')
  })

  it('menolak berkas yang bukan zip', () => {
    expect(() => bacaXlsx(new Uint8Array([1, 2, 3, 4]))).toThrow(/bukan \.xlsx/)
  })
})

describe('keBaris', () => {
  it('mengubah baris POS jadi kiriman', () => {
    const { baris: b, ringkas } = keBaris([JUDUL, baris()])
    expect(b).toHaveLength(1)
    expect(b[0]).toEqual({
      tanggal: '2026-08-17', order_no: 'INV-1', sku: 'PKG-0118-3',
      produk: 'Thinwall DM 200RB - Trs', qty: 2, omzet: 21000,
      lunas: true, cara_bayar: 'CASH', pelanggan: '',
    })
    expect(ringkas.omzet).toBe(21000)
    expect(ringkas.piutang).toBe(0)
  })

  it('TIDAK mengirim kolom pribadi', () => {
    const { baris: b } = keBaris([JUDUL, baris()])
    const kunci = Object.keys(b[0])
    for (const dilarang of ['sales email', 'profit', 'customer phone', 'qty_with_converter']) {
      expect(kunci).not.toContain(dilarang)
    }
    expect(JSON.stringify(b)).not.toContain('kasir@toko.test')
    expect(JSON.stringify(b)).not.toContain('3000')
  })

  it('paid 0 jadi belum lunas dan masuk piutang', () => {
    const { baris: b, ringkas } = keBaris([JUDUL, baris({
      paid: '0', 'payment type': 'TEMPO', 'customer name': 'MajaKoffie', amount: 385000,
    })])
    expect(b[0].lunas).toBe(false)
    expect(b[0].pelanggan).toBe('MajaKoffie')
    expect(ringkas.piutang).toBe(385000)
  })

  it('TEMPO yang sudah lunas tetap lunas, tapi cara bayarnya tercatat', () => {
    // Bedanya dengan tunai cuma di kolom cara_bayar -- itu satu-satunya cara
    // membedakan "hutang yang sudah dibayar" dari "bayar tunai di kasir".
    const { baris: b, ringkas } = keBaris([JUDUL, baris({
      paid: '1', 'payment type': 'TEMPO', 'customer name': 'Chery Bakes House',
    })])
    expect(b[0].lunas).toBe(true)
    expect(b[0].cara_bayar).toBe('TEMPO')
    expect(ringkas.piutang).toBe(0)
  })

  it('baris tanpa SKU TETAP dikirim dan dihitung', () => {
    // 39 baris begini di export sungguhan, Rp 915.500. Barang yang diketik manual
    // di kasir karena belum ada di master -- dibuang di sini artinya hilang
    // selamanya tanpa ada yang tahu stoknya tidak pernah berkurang.
    const { baris: b, ringkas } = keBaris([JUDUL, baris({
      'item sku': '', 'item name': 'kertas nasi roll',
    })])
    expect(b).toHaveLength(1)
    expect(b[0].sku).toBe('')
    expect(b[0].produk).toBe('kertas nasi roll')
    expect(ringkas.tanpaSku).toBe(1)
  })

  it('menerima tanggal berbentuk teks', () => {
    const { baris: b } = keBaris([JUDUL, baris({ 'order date': '2026-08-17 00:00:00' })])
    expect(b[0].tanggal).toBe('2026-08-17')
  })

  it('melewat baris kosong di ujung berkas tanpa mengeluh', () => {
    const { baris: b, ringkas } = keBaris([JUDUL, baris(), JUDUL.map(() => '')])
    expect(b).toHaveLength(1)
    expect(ringkas.tanpaTanggal).toBe(0)
  })

  it('menghitung baris berisi yang tanggalnya tidak terbaca', () => {
    const { ringkas } = keBaris([JUDUL, baris(), baris({ 'order date': 'entah' })])
    expect(ringkas.tanpaTanggal).toBe(1)
    expect(ringkas.dipakai).toBe(1)
  })

  it('mencatat rentang tanggal terkecil sampai terbesar', () => {
    const { ringkas } = keBaris([
      JUDUL,
      baris({ 'order date': SERIAL_17_AGU + 3 }),
      baris({ 'order date': SERIAL_17_AGU }),
      baris({ 'order date': SERIAL_17_AGU + 1 }),
    ])
    expect(ringkas.tanggalAwal).toBe('2026-08-17')
    expect(ringkas.tanggalAkhir).toBe('2026-08-20')
  })

  it('MENOLAK export jenis lain, menyebut kolom yang hilang', () => {
    // Export "Qty Produk Terjual" yang lama tidak punya `item sku`. Kalau
    // diteruskan, hasilnya angka stok yang salah tanpa satu pun tanda bahaya.
    const salah = ['product', 'variant', 'sku', 'group', 'sales qty']
    expect(() => keBaris([salah, ['a', 'b', 'c', 'd', 1]]))
      .toThrow(/"order date".*tidak ada/s)
    expect(() => keBaris([salah, ['a', 'b', 'c', 'd', 1]]))
      .toThrow(/Item Penjualan berdasarkan Tanggal/)
  })

  it('menolak berkas tanpa satu pun baris bertanggal', () => {
    expect(() => keBaris([JUDUL])).toThrow(/tidak ada satu pun baris/i)
  })

  it('menolak berkas kosong', () => {
    expect(() => keBaris([])).toThrow(/kosong/i)
  })
})

describe('parsePenjualan (berkas utuh)', () => {
  it('membaca .xlsx sampai jadi kiriman', () => {
    const { baris: b, ringkas } = parsePenjualan(bikinXlsx([
      JUDUL,
      baris(),
      baris({ paid: '0', 'payment type': 'TEMPO', 'customer name': 'Coffee Bawa', amount: 2405000 }),
    ]))
    expect(b).toHaveLength(2)
    expect(ringkas.piutang).toBe(2405000)
    expect(ringkas.omzet).toBe(2426000)
    expect(ringkas.tanggalAwal).toBe('2026-08-17')
  })

  it('semua kolom yang dibutuhkan memang ada di daftar KOLOM', () => {
    for (const judul of Object.values(KOLOM)) {
      expect(JUDUL).toContain(judul)
    }
  })
})
