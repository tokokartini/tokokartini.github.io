// Baca export POS "Item Penjualan berdasarkan Tanggal" (.xlsx) jadi baris yang
// siap dikirim ke `ganti_penjualan()` di Supabase.
//
// Kenapa dibaca di browser, bukan dikirim mentah ke server: file itu punya 69
// kolom, dan yang dipakai hitungan stok cuma 9. Sisanya termasuk email karyawan
// (2.528 baris di contoh sepekan), nomor HP + alamat pelanggan, HPP, profit, dan
// komisi. Dipotong di sini, data itu tidak pernah meninggalkan HP yang mengupload.
// Payload-nya juga jadi belasan kali lebih kecil.
//
// Kenapa TIDAK pakai SheetJS: versi di npm sudah lama tidak diperbarui (masih
// membawa CVE prototype pollution) dan ~900KB — mahal untuk PWA yang dibuka lewat
// kuota. Yang dibutuhkan cuma membuka zip lalu membaca dua berkas XML, dan bentuk
// berkasnya tetap karena selalu dibuat mesin yang sama.
//
// Berkas .xlsx itu zip berisi XML:
//   xl/sharedStrings.xml       semua teks, dipakai berulang lewat nomor
//   xl/worksheets/sheet1.xml   selnya sendiri
import { unzipSync, strFromU8 } from 'fflate'

// Nama kolom yang dipakai, apa adanya dari baris judul export.
// Kalau salah satu tidak ada, seluruh berkas ditolak — lihat catatan di bacaFile().
export const KOLOM = {
  tanggal: 'order date',
  order_no: 'order no',
  sku: 'item sku',
  produk: 'item name',
  qty: 'qty',
  omzet: 'amount',
  paid: 'paid',
  cara_bayar: 'payment type',
  pelanggan: 'customer name',
}

// Angka di kolom tanggal itu "hari sejak 1899-12-30" (penanggalan Excel).
// Rentang yang masuk akal: 2010-01-01 sampai 2100-01-01. Dipakai membedakan
// tanggal dari angka biasa TANPA harus ikut membaca xl/styles.xml — aman karena
// cuma diterapkan pada satu kolom yang memang sudah kita tahu isinya tanggal.
const SERIAL_MIN = 40179
const SERIAL_MAKS = 73051

export function serialKeTanggal(n) {
  const ms = Date.UTC(1899, 11, 30) + Math.round(n) * 86400000
  return new Date(ms).toISOString().slice(0, 10)
}

// Ambil isi tiap <t>...</t> di dalam satu <si>. Teks yang diberi format sebagian
// (mis. separuh tebal) dipecah jadi beberapa <r><t>, jadi harus disambung. <si/>
// yang kosong tetap harus menempati nomornya, kalau tidak seluruh teks bergeser.
const RE_SI = /<si(?:\s[^>]*)?(?:\/>|>([\s\S]*?)<\/si>)/g
const RE_T = /<t(?:\s[^>]*)?(?:\/>|>([\s\S]*?)<\/t>)/g

function bacaSharedStrings(xml) {
  const hasil = []
  RE_SI.lastIndex = 0
  let si
  while ((si = RE_SI.exec(xml))) {
    const dalam = si[1] || ''
    let teks = ''
    RE_T.lastIndex = 0
    let t
    while ((t = RE_T.exec(dalam))) teks += lepasEntitas(t[1] || '')
    hasil.push(teks)
  }
  return hasil
}

function lepasEntitas(s) {
  return s
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(Number(d)))
    .replace(/&amp;/g, '&')
}

// "BQ12" -> 68 (nomor kolom, mulai 0). Dipakai supaya sel yang KOSONG tetap
// menggeser kolom — di xlsx sel kosong memang tidak ditulis sama sekali, jadi
// membaca berurutan tanpa melihat alamatnya bikin kolom melenceng.
export function nomorKolom(ref) {
  let n = 0
  for (const ch of ref) {
    const k = ch.charCodeAt(0)
    if (k < 65 || k > 90) break
    n = n * 26 + (k - 64)
  }
  return n - 1
}

function bacaSheet(xml, shared) {
  const baris = []
  const rows = xml.split('<row')
  for (let i = 1; i < rows.length; i++) {
    const isiBaris = rows[i].split('</row>')[0]
    const sel = []
    const cs = isiBaris.split('<c ')
    for (let j = 1; j < cs.length; j++) {
      const c = cs[j]
      const kepala = c.split('>')[0]
      const ref = (kepala.match(/r="([A-Z]+\d+)"/) || [])[1] || ''
      const tipe = (kepala.match(/t="([^"]+)"/) || [])[1] || ''
      const idx = ref ? nomorKolom(ref) : sel.length
      let nilai = ''
      if (tipe === 'inlineStr') {
        const m = c.match(/<t[^>]*>([\s\S]*?)<\/t>/)
        nilai = m ? lepasEntitas(m[1]) : ''
      } else {
        const m = c.match(/<v>([\s\S]*?)<\/v>/)
        const mentah = m ? lepasEntitas(m[1]) : ''
        nilai = tipe === 's' ? (shared[Number(mentah)] ?? '') : mentah
      }
      while (sel.length < idx) sel.push('')
      sel[idx] = nilai
    }
    baris.push(sel)
  }
  return baris
}

/** Buka .xlsx (Uint8Array / ArrayBuffer) jadi array of array. Lembar pertama. */
export function bacaXlsx(data) {
  const buf = data instanceof Uint8Array ? data : new Uint8Array(data)
  let isi
  try {
    isi = unzipSync(buf)
  } catch (e) {
    throw new Error('Berkas ini bukan .xlsx yang bisa dibaca. Pastikan yang dipilih hasil export POS, bukan .csv atau .pdf.')
  }
  const namaSheet = Object.keys(isi)
    .filter((n) => /^xl\/worksheets\/sheet\d+\.xml$/.test(n))
    .sort()
  if (!namaSheet.length) throw new Error('Berkas .xlsx tidak berisi lembar kerja.')
  const shared = isi['xl/sharedStrings.xml']
    ? bacaSharedStrings(strFromU8(isi["xl/sharedStrings.xml"]))
    : []
  return bacaSheet(strFromU8(isi[namaSheet[0]]), shared)
}

function angka(x) {
  if (x === '' || x === null || x === undefined) return 0
  const n = Number(String(x).replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

function tanggalDari(x) {
  const s = String(x ?? '').trim()
  if (!s) return ''
  // Sudah berupa teks tanggal (sebagian export menulis begini).
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]}`
  const n = Number(s)
  if (Number.isFinite(n) && n >= SERIAL_MIN && n <= SERIAL_MAKS) return serialKeTanggal(n)
  return ''
}

/**
 * Ubah tabel mentah jadi baris untuk `ganti_penjualan()`.
 *
 * Kembalian: { baris, ringkas }
 *   ringkas: { total, dipakai, tanpaTanggal, tanpaSku, tanggalAwal, tanggalAkhir,
 *              omzet, piutang }
 *
 * Baris tanpa SKU TETAP dikirim. Di export 17-23 Agu ada 39 baris begitu senilai
 * Rp 915.500 -- barang yang diketik manual di kasir karena belum ada di master.
 * Itu justru daftar kerja: barang terjual yang stoknya tidak dilacak siapa pun.
 * Dibuang di sini artinya hilang selamanya tanpa ada yang tahu.
 */
export function keBaris(tabel) {
  if (!tabel || !tabel.length) throw new Error('Berkasnya kosong.')
  const judul = tabel[0].map((c) => String(c ?? '').trim().toLowerCase())
  const K = {}
  const hilang = []
  for (const [nama, judulnya] of Object.entries(KOLOM)) {
    const i = judul.indexOf(judulnya)
    if (i < 0) hilang.push(judulnya)
    K[nama] = i
  }
  // Ditolak keras, bukan diteruskan dengan kolom kosong. Export POS yang SALAH
  // JENIS (mis. "Qty Produk Terjual" yang lama) tidak punya `item sku`, dan kalau
  // diteruskan hasilnya angka stok yang salah tanpa satu pun tanda bahaya.
  if (hilang.length) {
    throw new Error(
      `Kolom ${hilang.map((h) => `"${h}"`).join(', ')} tidak ada di berkas ini. ` +
      'Yang dibutuhkan export "Item Penjualan berdasarkan Tanggal".'
    )
  }

  const baris = []
  let tanpaTanggal = 0
  let tanpaSku = 0
  let omzet = 0
  let piutang = 0
  let awal = ''
  let akhir = ''

  for (let i = 1; i < tabel.length; i++) {
    const r = tabel[i]
    if (!r || !r.length) continue
    const tanggal = tanggalDari(r[K.tanggal])
    if (!tanggal) {
      // Baris kosong di ujung berkas itu wajar; yang ADA isinya tapi tanpa
      // tanggal dihitung supaya kelihatan di laporan.
      if (r.some((c) => String(c ?? '').trim())) tanpaTanggal++
      continue
    }
    const sku = String(r[K.sku] ?? '').trim()
    if (!sku) tanpaSku++
    const nilai = angka(r[K.omzet])
    // `paid` = "1" lunas, "0" belum. TEMPO yang sudah dibayar ikut jadi lunas,
    // dan cara_bayar yang membedakannya dari tunai biasa.
    const lunas = String(r[K.paid] ?? '').trim() !== '0'
    omzet += nilai
    if (!lunas) piutang += nilai
    if (!awal || tanggal < awal) awal = tanggal
    if (!akhir || tanggal > akhir) akhir = tanggal
    baris.push({
      tanggal,
      order_no: String(r[K.order_no] ?? '').trim(),
      sku,
      produk: String(r[K.produk] ?? '').trim(),
      qty: angka(r[K.qty]),
      omzet: nilai,
      lunas,
      cara_bayar: String(r[K.cara_bayar] ?? '').trim(),
      pelanggan: String(r[K.pelanggan] ?? '').trim(),
    })
  }

  if (!baris.length) {
    throw new Error('Tidak ada satu pun baris bertanggal di berkas ini.')
  }

  return {
    baris,
    ringkas: {
      total: tabel.length - 1,
      dipakai: baris.length,
      tanpaTanggal,
      tanpaSku,
      tanggalAwal: awal,
      tanggalAkhir: akhir,
      omzet,
      piutang,
    },
  }
}

/** Jalan pintas: berkas -> baris siap kirim. */
export function parsePenjualan(data) {
  return keBaris(bacaXlsx(data))
}
