export function totalQty(units) {
  return units.reduce((sum, u) => sum + (Number(u.qty) || 0) * u.mult, 0)
}
