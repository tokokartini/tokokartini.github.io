// Salinan entri terbuka per rak, disimpan di HP.
//
// Antrian offline (`outbox.js`) cuma memuat hitungan yang GAGAL terkirim. Hitungan
// yang sudah telanjur mendarat di server tidak ada di sana -- dia dibaca ulang dari
// Supabase tiap kali halaman dibuka. Tanpa cache ini, karyawan yang menghitung 80
// produk pagi hari (sinyal ada) lalu me-reload aplikasi di gudang tanpa sinyal akan
// melihat daftar "Hasil rak ini" KOSONG, mengira hitungannya hilang, dan menghitung
// ulang dari nol.
//
// Isinya cuma entri yang belum ter-upload: yang sudah ter-upload memang disembunyikan
// dari daftar, jadi tidak perlu ikut disimpan dan ukurannya tetap kecil.

const KEY = 'so-entries-v1'

// Pagar ukuran. Satu rak realistis puluhan sampai ratusan produk; batas ini cuma
// mencegah localStorage jebol kalau suatu hari ada rak raksasa.
const BATAS = 500

function kunci(rack, uid) {
  return `${uid}|${rack}`
}

function bacaSemua(store) {
  try {
    const isi = JSON.parse(store?.getItem(KEY) || 'null')
    return isi && typeof isi === 'object' && !Array.isArray(isi) ? isi : {}
  } catch {
    return {}
  }
}

export function bacaEntriCache(rack, uid, store = globalThis.localStorage) {
  const slot = bacaSemua(store)[kunci(rack, uid)]
  if (!slot) return { milik: [], lain: [] }
  return {
    milik: Array.isArray(slot.milik) ? slot.milik : [],
    lain: Array.isArray(slot.lain) ? slot.lain : [],
  }
}

// `milik` = entri orang ini di rak ini. `lain` = entri terbuka rekan lain, dipakai
// peringatan "sudah dihitung <nama>" -- itu justru paling berguna offline, karena di
// sana dua orang tidak bisa saling lihat lewat server.
export function tulisEntriCache(rack, uid, { milik = [], lain = [] } = {}, store = globalThis.localStorage) {
  const semua = bacaSemua(store)
  semua[kunci(rack, uid)] = {
    milik: milik.filter((e) => !e.uploaded_at).slice(0, BATAS),
    lain: lain.slice(0, BATAS),
  }
  try {
    store?.setItem(KEY, JSON.stringify(semua))
    return true
  } catch {
    // Kuota penuh. Tidak fatal: cache ini cuma salinan baca -- sumber kebenarannya
    // tetap server, dan hitungan yang belum terkirim ada di outbox, bukan di sini.
    return false
  }
}

export function hapusEntriCache(store = globalThis.localStorage) {
  try { store?.removeItem(KEY) } catch { /* diblokir */ }
}
