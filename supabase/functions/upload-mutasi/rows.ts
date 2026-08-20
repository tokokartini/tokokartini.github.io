// Penyusun baris untuk tab Mutasi. File ini SENGAJA murni -- tanpa import Deno dan
// tanpa jaringan -- supaya bisa diuji Vitest (rows.test.ts) di laptop, sementara
// index.ts tetap satu-satunya yang menyentuh Supabase dan Sheets.
//
// Kembar dengan functions/upload-rak/rows.ts, tapi sengaja tidak berbagi file:
// tab Log punya format 9 kolom yang sudah dikunci empat formula output, dan
// menyatukan keduanya berarti perubahan kecil di mutasi bisa menggoyang Log.

export type Unit = { sku: string; variant: string; mult: number; qty: number }

export type Movement = {
  updated_at: string
  username: string
  jenis: string
  from_loc: string
  to_loc: string
  nota: string | null
  product_name: string
  units: Unit[] | null
  qty_total: number | null
}

export type MutasiRow = (string | number)[]

export function wib(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 7 * 3600 * 1000)
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

// Satuan dasar = mult 1. Kalau master tidak punya satuan mult 1 untuk produk itu,
// ambil mult terkecil supaya qty_total (yang selalu dalam satuan terkecil) tetap
// dilaporkan di satuan yang paling mendekati, bukan di satuan karton.
export function baseUnitOf(units: Unit[] | null): Unit | null {
  if (!units || !units.length) return null
  return (
    units.find((u) => u.mult === 1) ??
    units.reduce((smallest, u) => (u.mult < smallest.mult ? u : smallest), units[0])
  )
}

// Rincian satuan asli yang diketik petugas, mis. "2 Krtn + 5 Pack". Untuk dibaca
// manusia saat mencocokkan ulang ke fisik barang -- angka yang dihitung rekap
// tetap kolom Qty (satuan dasar), bukan teks ini.
//
// Filter !== 0 (bukan > 0) mengikuti alasan yang sama seperti di upload-rak:
// CountForm tidak dibungkus <form>, jadi min="0" tidak pernah divalidasi, dan
// satu satuan boleh negatif selama gabungannya tetap positif. Kalau dipakai > 0,
// satuan negatif hilang dari Rincian sementara Qty tetap menghitungnya.
export function rincianText(units: Unit[] | null): string {
  if (!units) return ''
  return [...units]
    .filter((u) => Number(u.qty) !== 0)
    .sort((a, b) => b.mult - a.mult)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}

// Kolom: Waktu, Staff, Jenis, Dari, Ke, Produk, Rincian, Qty, Satuan, SKU, Nota --
// harus tetap 11 dan urutannya persis begitu; tab Rekap Mutasi menunjuk kolom ini
// lewat array literal di scripts/add_mutasi.py.
//
// Kolom Jenis disimpan apa adanya dari DB, bukan disimpulkan dari nama lokasi.
// Nama lokasi pernah berubah total ("Rak 1" jadi "Gudang Packaging") dan baris
// lama harus tetap berarti sama.
export function buildMutasiRows(moves: Movement[]): { rows: MutasiRow[]; skipped: string[] } {
  const rows: MutasiRow[] = []
  const skipped: string[] = []

  for (const m of moves) {
    const baseUnit = baseUnitOf(m.units)
    // Baris tanpa satuan tidak bisa dinamai SKU-nya. Dilewati, bukan bikin seluruh
    // surat jalan gagal -- barang lain di surat jalan yang sama tetap harus masuk.
    if (!baseUnit) {
      skipped.push(m.product_name)
      continue
    }

    rows.push([
      wib(m.updated_at),
      m.username,
      m.jenis,
      m.from_loc,
      m.to_loc,
      m.product_name,
      rincianText(m.units),
      Number(m.qty_total ?? 0),
      baseUnit.variant,
      baseUnit.sku,
      m.nota ?? '',
    ])
  }

  return { rows, skipped }
}
