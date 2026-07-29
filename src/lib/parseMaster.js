// Parsing Master Pricelist -> daftar produk. Fungsi murni supaya bisa diuji.
// KEMBARAN: supabase/functions/sync-produk/index.ts memuat salinan persis logika
// ini (Edge Function tidak bisa mengimpor dari src/). Ubah keduanya bersamaan.

// (kolom SKU, kolom satuan, kolom isi) — isi null = grosir (isi 1)
const UNIT_SLOTS = [[28, 6, null], [29, 8, 7], [30, 10, 9], [31, 12, 11]]

export function parseIsi(raw) {
  const s = String(raw ?? '').trim()
  if (!s || s === '-') return null
  const cleaned = s.replace(/\./g, '').replace(',', '.')
  // Python's float("") raises ValueError -> None; JS's Number("") is 0 (finite),
  // so an all-dot input like "." (thousands-sep stripped to "") must be rejected
  // explicitly or it would wrongly parse as 0 instead of null.
  if (!cleaned) return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

export function parseMaster(rows) {
  const products = []
  const seen = new Set()
  let skipped = 0
  let dupes = 0
  for (const raw of rows.slice(2)) {
    const row = [...raw]
    while (row.length < 32) row.push('')
    const name = String(row[3] ?? '').trim()
    if (!name || String(row[0] ?? '').trim().startsWith('===')) continue
    const units = []
    UNIT_SLOTS.forEach(([skuI, satI, isiI], order) => {
      const sku = String(row[skuI] ?? '').trim()
      if (!sku) return
      const satuan = String(row[satI] ?? '').trim()
      if (!satuan) { skipped++; return }
      const isi = isiI === null ? 1 : parseIsi(row[isiI])
      units.push({ sku, satuan, isi, order })
    })
    if (!units.length) continue
    const isis = units.map((u) => u.isi).filter(Boolean)
    const base = isis.length ? Math.max(...isis) : 1
    const broken = units.some((u) => u.isi === null)
    for (const u of units) {
      if (seen.has(u.sku)) { dupes++; continue }
      seen.add(u.sku)
      const mult = broken || !u.isi ? 1 : base / u.isi
      products.push({
        sku: u.sku,
        product_name: name,
        variant: u.satuan,
        mult: Math.round(mult * 10000) / 10000,
        unit_order: u.order,
        category: String(row[0] ?? '').trim(),
        brand: String(row[2] ?? '').trim(),
        active: true,
      })
    }
  }
  return { products, skipped, dupes }
}
