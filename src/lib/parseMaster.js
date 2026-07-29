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
    // Mirrors scripts/sync_products.py:34 (`row = list(raw) + [""] * (32 - len(raw))`),
    // where the padding is load-bearing: Python raises IndexError on a short list.
    // In JS every field read below goes through `row[i] ?? ''`, so an out-of-bounds
    // read already returns '' and this loop is defensive-only (dead for behavior)
    // here. Keep it anyway so this stays a faithful mirror of the Python authority.
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
    // filter(Boolean) mirrors scripts/sync_products.py:51's `if u["isi"]` truthy
    // filter. It is provably unobservable in this algorithm: a null isi only
    // appears when broken=true (every mult below gets forced to 1, so base is
    // never used), and 0 can only win Math.max when every isi in the row is 0 --
    // in which case every unit takes the `!u.isi` branch anyway, again bypassing
    // base. Kept for exact fidelity with the Python reference, not because
    // removing it would change any output.
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
        // Half-up vs Python round()'s half-to-even: of all integer base/isi pairs up
        // to 1000, 1.096 disagree by 1 unit in the 4th decimal (e.g. 33/32 -> Python
        // 1.0312, JS 1.0313; isi is always a multiple of 32 in those cases). Known,
        // accepted +/-0.0001 divergence from scripts/sync_products.py -- not a bug.
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
