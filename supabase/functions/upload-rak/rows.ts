// Pemilih baris untuk tab Log. File ini SENGAJA murni -- tanpa import Deno dan
// tanpa jaringan -- supaya bisa diuji Vitest (rows.test.ts) di laptop, sementara
// index.ts tetap satu-satunya yang menyentuh Supabase dan Sheets.
//
// Satu entri = SATU baris. Kolom Rincian berisi satuan asli yang diketik petugas
// (mis. "2 Krtn + 3 Pack + 5 Pcs"), sementara kolom Qty tetap nilai satuan dasar
// dari qty_total. Kolom qty_total sudah dihitung frontend lewat totalQty() di
// src/lib/convert.js; jangan dijumlah ulang di sini supaya tidak ada dua sumber
// kebenaran.

export type Unit = { sku: string; variant: string; mult: number; qty: number }

export type Entry = {
  updated_at: string
  username: string
  rack: string
  product_name: string
  units: Unit[] | null
  qty_total: number | null
  expired_date: string | null
}

export type LogRow = (string | number)[]

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

// Rincian satuan asli yang diketik petugas, mis. "2 Krtn + 3 Pack + 5 Pcs".
// Hanya untuk dibaca manusia saat mencocokkan ulang ke rak -- angka yang
// dihitung tab output tetap kolom Qty (satuan dasar), bukan teks ini.
export function rincianText(units: Unit[] | null): string {
  if (!units) return ''
  return [...units]
    .filter((u) => Number(u.qty) > 0)
    .sort((a, b) => b.mult - a.mult)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}

// Kolom: Waktu, Staff, rack, Produk, Rincian, Qty, Satuan, ED, SKU -- harus tetap
// 9 dan urutannya persis begitu; Rekap/Template Olsera/Arsip Harian/Arsip Bulanan
// menunjuk kolom ini lewat array literal di scripts/setup_sheet.py.
export function buildLogRows(entries: Entry[]): { rows: LogRow[]; skipped: string[] } {
  const rows: LogRow[] = []
  const skipped: string[] = []

  for (const e of entries) {
    const baseUnit = baseUnitOf(e.units)
    // Entri tanpa satuan tidak bisa dinamai SKU-nya. Dilewati, bukan bikin
    // seluruh upload gagal -- entri lain di rak yang sama tetap harus masuk.
    if (!baseUnit) {
      skipped.push(e.product_name)
      continue
    }

    rows.push([
      wib(e.updated_at),
      e.username,
      e.rack,
      e.product_name,
      rincianText(e.units),
      Number(e.qty_total ?? 0),
      baseUnit.variant,
      e.expired_date ?? '',
      baseUnit.sku,
    ])
  }

  return { rows, skipped }
}
