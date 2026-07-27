import { describe, it, expect } from 'vitest'
import { totalQty } from './convert'

const units = [
  { sku: 'A1', variant: 'Krtn (15 Kg)', mult: 60, qty: 1 },
  { sku: 'A2', variant: 'Kg', mult: 4, qty: 2 },
  { sku: 'A3', variant: '250gr', mult: 1, qty: '' },
]

describe('totalQty', () => {
  it('jumlahkan qty × mult, kosong = 0', () => {
    expect(totalQty(units)).toBe(68)
  })
  it('semua kosong = 0', () => {
    expect(totalQty([{ mult: 60, qty: '' }])).toBe(0)
  })
})
