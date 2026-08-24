// Cache entri stock opname per rak. Mesinnya di `cacheDaftar.js`.
//
// `milik` = entri orang ini di rak ini. `lain` = entri terbuka rekan lain, dipakai
// peringatan "sudah dihitung <nama>" -- itu justru paling berguna offline, karena di
// sana dua orang tidak bisa saling lihat lewat server.

import { buatCacheDaftar } from './cacheDaftar'

const cache = buatCacheDaftar({ key: 'so-entries-v1', bagian: ['milik', 'lain'] })

const ruang = (rack, uid) => `${uid}|${rack}`

export function bacaEntriCache(rack, uid, store) {
  return cache.baca(ruang(rack, uid), store)
}

export function tulisEntriCache(rack, uid, isi, store) {
  return cache.tulis(ruang(rack, uid), isi, store)
}

export const hapusEntriCache = cache.hapus
