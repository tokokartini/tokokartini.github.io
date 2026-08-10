// Cache daftar produk di localStorage.
//
// Tanpa ini, tiap kali halaman hitung dibuka aplikasi menarik ~2772 baris produk
// (3 permintaan @1000) — di gudang bersinyal tipis itu berarti layar kosong lama
// dan boros kuota, dikali jumlah karyawan dikali berapa kali mereka ganti rak.
//
// Produk hanya berubah lewat sync (job malam 03:00 atau tombol admin), dan tiap
// sync yang berhasil menulis baris ke `sync_runs`. Jadi `ran_at` sync terakhir
// yang OK dipakai sebagai penanda versi: kalau penandanya sama dengan yang
// tersimpan, isi cache dijamin sama dan seluruh unduhan bisa dilewati — cukup
// satu permintaan kecil. Jumlah produk ikut dicek supaya perubahan langsung di
// tabel `products` (bukan lewat sync) tidak lolos diam-diam.

const KEY = 'so-products-v1'

// Kolom yang benar-benar dipakai groupProducts. `id`/`active` tidak ikut supaya
// cache ~30% lebih kecil (2772 baris masih di bawah kuota 5 MB localStorage).
const KOLOM = ['sku', 'product_name', 'variant', 'mult', 'unit_order', 'category', 'brand']

export const PRODUCT_COLUMNS = KOLOM.join(', ')

function ramping(p) {
  const out = {}
  for (const k of KOLOM) out[k] = p[k]
  return out
}

export function bacaCache(store = globalThis.localStorage) {
  try {
    const raw = store?.getItem(KEY)
    if (!raw) return null
    const c = JSON.parse(raw)
    if (!c || !Array.isArray(c.products) || c.products.length === 0) return null
    return { stamp: c.stamp ?? null, count: c.count ?? c.products.length, products: c.products }
  } catch {
    // JSON rusak / localStorage diblokir (mode privat) — anggap saja tidak ada cache.
    return null
  }
}

export function tulisCache(stamp, products, store = globalThis.localStorage) {
  try {
    store?.setItem(KEY, JSON.stringify({ stamp, count: products.length, products: products.map(ramping) }))
    return true
  } catch {
    // Kuota penuh tidak boleh menggagalkan hitungan — cache cuma pemercepat.
    return false
  }
}

export function hapusCache(store = globalThis.localStorage) {
  try {
    store?.removeItem(KEY)
  } catch {
    /* diabaikan */
  }
}

// `fresh` = { stamp, count } hasil satu permintaan kecil ke server.
export function cacheMasihSah(cache, fresh) {
  if (!cache || !fresh) return false
  if (!cache.stamp || !fresh.stamp) return false // belum pernah sync: jangan percaya cache
  if (typeof fresh.count !== 'number') return false
  return cache.stamp === fresh.stamp && cache.count === fresh.count
}
