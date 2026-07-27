import { describe, it, expect } from 'vitest'
import { groupProducts, filterGroups } from './groupProducts'

const products = [
  { sku: 'B2', product_name: 'Mentega Simas 15kg', variant: 'Kg', mult: 4, unit_order: 1, category: 'Bahan', brand: 'Simas' },
  { sku: 'B1', product_name: 'Mentega Simas 15kg', variant: 'Krtn (15 Kg)', mult: 60, unit_order: 0, category: 'Bahan', brand: 'Simas' },
  { sku: 'C1', product_name: 'Mika DP 7C', variant: 'Pack', mult: 1, unit_order: 0, category: 'Mika', brand: 'DP' },
]

describe('groupProducts', () => {
  it('group per nama, units urut unit_order', () => {
    const g = groupProducts(products)
    expect(g).toHaveLength(2)
    expect(g[0].units.map((u) => u.sku)).toEqual(['B1', 'B2'])
  })
})

describe('filterGroups', () => {
  const groups = groupProducts(products)
  it('cari nama', () => {
    expect(filterGroups(groups, 'mentega')).toHaveLength(1)
  })
  it('cari sku', () => {
    expect(filterGroups(groups, 'c1')[0].name).toBe('Mika DP 7C')
  })
  it('query kosong = []', () => {
    expect(filterGroups(groups, '  ')).toEqual([])
  })
})
