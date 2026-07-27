export function totalQty(units) {
  return units.reduce((sum, u) => sum + (Number(u.qty) || 0) * u.mult, 0)
}

export function breakdownText(units) {
  return units
    .filter((u) => (Number(u.qty) || 0) > 0)
    .map((u) => `${Number(u.qty)} ${u.variant}`)
    .join(' + ')
}
