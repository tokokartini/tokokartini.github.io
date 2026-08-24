// Cache baris surat jalan per pasangan lokasi. Mesinnya di `cacheDaftar.js`.
//
// Ruangnya asal + tujuan + pemilik, bukan cuma pemilik: satu orang bisa menyusun
// dua surat jalan berbeda (mis. ke Area Display dan ke gudang lain) dan daftarnya
// tidak boleh tercampur.

import { buatCacheDaftar } from './cacheDaftar'

const cache = buatCacheDaftar({ key: 'so-movements-v1', bagian: ['milik'] })

const ruang = (from, to, uid) => `${uid}|${from}|${to}`

export function bacaMutasiCache(from, to, uid, store) {
  return cache.baca(ruang(from, to, uid), store).milik
}

export function tulisMutasiCache(from, to, uid, rows, store) {
  return cache.tulis(ruang(from, to, uid), { milik: rows }, store)
}

export const hapusMutasiCache = cache.hapus
