export function groupProducts(products) {
  const map = new Map()
  for (const p of products) {
    let g = map.get(p.product_name)
    if (!g) {
      g = { name: p.product_name, category: p.category, brand: p.brand, units: [] }
      map.set(p.product_name, g)
    }
    g.units.push({ sku: p.sku, variant: p.variant, mult: Number(p.mult), unit_order: p.unit_order })
  }
  for (const g of map.values()) g.units.sort((a, b) => a.unit_order - b.unit_order)
  return [...map.values()]
}

export function filterGroups(groups, query) {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return groups.filter(
    (g) =>
      g.name.toLowerCase().includes(q) ||
      g.units.some((u) => u.sku.toLowerCase().includes(q)),
  )
}
