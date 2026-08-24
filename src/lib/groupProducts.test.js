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
  const nama = (q) => filterGroups(groups, q).map((g) => g.name)

  it('cari nama', () => {
    expect(filterGroups(groups, 'mentega')).toHaveLength(1)
  })
  it('cari sku', () => {
    expect(filterGroups(groups, 'c1')[0].name).toBe('Mika DP 7C')
  })
  it('query kosong = []', () => {
    expect(filterGroups(groups, '  ')).toEqual([])
  })
  it('urutan kata bebas', () => {
    expect(nama('simas mentega')).toEqual(['Mentega Simas 15kg'])
    expect(nama('mentega simas')).toEqual(['Mentega Simas 15kg'])
  })
  it('kata terpisah jauh tetap ketemu', () => {
    expect(nama('mentega 15kg')).toEqual(['Mentega Simas 15kg'])
    expect(nama('7c mika')).toEqual(['Mika DP 7C'])
  })
  it('satu kata tidak cocok = tidak ketemu', () => {
    expect(nama('mentega mika')).toEqual([])
  })
  it('spasi berlebih diabaikan', () => {
    expect(nama('  mentega   simas  ')).toEqual(['Mentega Simas 15kg'])
  })
  it('SKU utuh menang atas cocok sebagian nama', () => {
    const g = groupProducts([
      ...products,
      { sku: 'ZZ', product_name: 'Kardus C1 Polos', variant: 'Pcs', mult: 1, unit_order: 0, category: '', brand: '' },
    ])
    expect(filterGroups(g, 'c1')[0].name).toBe('Mika DP 7C')
  })
  it('nama yang diawali query naik ke atas', () => {
    const g = groupProducts([
      { sku: 'A1', product_name: 'Gula Pasir Curah', variant: 'Pcs', mult: 1, unit_order: 0, category: '', brand: '' },
      { sku: 'A2', product_name: 'Kopi Gula Aren', variant: 'Pcs', mult: 1, unit_order: 0, category: '', brand: '' },
    ])
    expect(filterGroups(g, 'gula').map((x) => x.name)).toEqual(['Gula Pasir Curah', 'Kopi Gula Aren'])
  })
  it('urutan stabil saat skornya seri', () => {
    const g = groupProducts([
      { sku: 'A2', product_name: 'Kresek B', variant: 'Pcs', mult: 1, unit_order: 0, category: '', brand: '' },
      { sku: 'A1', product_name: 'Kresek A', variant: 'Pcs', mult: 1, unit_order: 0, category: '', brand: '' },
    ])
    expect(filterGroups(g, 'kresek').map((x) => x.name)).toEqual(['Kresek A', 'Kresek B'])
  })
})
