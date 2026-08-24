// Mesin cache daftar baris per "ruang kerja", disimpan di localStorage.
//
// Antrian (`antrian.js`) cuma memuat ketikan yang GAGAL terkirim. Baris yang sudah
// telanjur mendarat di server tidak ada di sana -- dia dibaca ulang dari Supabase
// tiap kali halaman dibuka. Tanpa cache ini, karyawan yang bekerja pagi hari
// (sinyal ada) lalu me-reload aplikasi di gudang tanpa sinyal melihat daftarnya
// KOSONG, mengira hasilnya hilang, dan mengetik ulang dari nol.
//
// Isinya cuma baris yang belum ter-upload: yang sudah ter-upload memang
// disembunyikan dari daftar, jadi tidak perlu ikut disimpan dan ukurannya kecil.

// Pagar ukuran. Satu ruang kerja realistis puluhan sampai ratusan baris; batas ini
// cuma mencegah localStorage jebol kalau suatu hari ada yang raksasa.
const BATAS = 500

export function buatCacheDaftar({ key, bagian = ['milik'] }) {
  const kosong = () => Object.fromEntries(bagian.map((b) => [b, []]))

  function semua(store) {
    try {
      const isi = JSON.parse(store?.getItem(key) || 'null')
      return isi && typeof isi === 'object' && !Array.isArray(isi) ? isi : {}
    } catch {
      return {}
    }
  }

  function baca(ruang, store = globalThis.localStorage) {
    const slot = semua(store)[ruang]
    if (!slot) return kosong()
    return Object.fromEntries(
      bagian.map((b) => [b, Array.isArray(slot[b]) ? slot[b] : []]),
    )
  }

  function tulis(ruang, isi = {}, store = globalThis.localStorage) {
    const data = semua(store)
    data[ruang] = Object.fromEntries(
      bagian.map((b) => [b, (isi[b] || []).filter((r) => !r.uploaded_at).slice(0, BATAS)]),
    )
    try {
      store?.setItem(key, JSON.stringify(data))
      return true
    } catch {
      // Kuota penuh. Tidak fatal: cache ini cuma salinan baca -- sumber kebenarannya
      // tetap server, dan ketikan yang belum terkirim ada di antrian, bukan di sini.
      return false
    }
  }

  function hapus(store = globalThis.localStorage) {
    try { store?.removeItem(key) } catch { /* diblokir */ }
  }

  return { KEY: key, baca, tulis, hapus }
}
