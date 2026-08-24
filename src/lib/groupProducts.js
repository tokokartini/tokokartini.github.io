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

// Cari produk. Tiap kata dicocokkan sendiri-sendiri, jadi URUTANNYA BEBAS.
//
// Versi lama satu `includes` atas seluruh query, jadi "simas mentega" tidak ketemu
// apa-apa padahal "mentega simas" ketemu -- dan nama produk di master panjang serta
// tidak konsisten urutannya ("Kresek HD TAXI 15 Putih" vs "Mika DP 7C"), sehingga
// karyawan harus menebak kata pertamanya dengan benar.
//
// Hasilnya diurutkan supaya yang paling mungkin dimaksud ada di atas -- daftar di
// layar dipotong, jadi urutan menentukan apa yang benar-benar kelihatan.
export function filterGroups(groups, query) {
  const kata = query.trim().toLowerCase().split(/\s+/).filter(Boolean)
  if (!kata.length) return []

  const cocok = []
  for (const g of groups) {
    const nama = g.name.toLowerCase()
    const sku = g.units.map((u) => (u.sku || '').toLowerCase())
    const jerami = `${nama} ${sku.join(' ')}`
    if (!kata.every((k) => jerami.includes(k))) continue
    cocok.push({ g, skor: skorCocok(nama, sku, kata) })
  }
  // Skor besar dulu; seri diputus nama supaya urutannya tidak berubah-ubah sendiri.
  cocok.sort((a, b) => b.skor - a.skor || a.g.name.localeCompare(b.g.name))
  return cocok.map((c) => c.g)
}

function skorCocok(nama, sku, kata) {
  const gabung = kata.join(' ')
  if (sku.some((s) => s === gabung)) return 5      // SKU diketik utuh
  if (nama === gabung) return 4                     // nama persis
  if (nama.startsWith(gabung)) return 3             // nama diawali query apa adanya
  if (nama.includes(gabung)) return 2               // query utuh ada di nama
  if (kata.every((k) => nama.includes(k))) return 1 // semua kata ada di nama, acak urutan
  return 0                                          // sebagian cocoknya cuma lewat SKU
}
