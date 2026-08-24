// Identitas login terakhir, disimpan di HP.
//
// Access token Supabase cuma berlaku 1 jam. Kalau karyawan me-reload aplikasi di
// gudang tanpa sinyal setelah lewat 1 jam, auth-js gagal menyegarkan token dan
// `getSession()` mengembalikan null -- karyawan ditendang ke halaman login, padahal
// login pun butuh sinyal. Hitungannya tidak hilang (masih di antrian), tapi kerjanya
// berhenti di tengah gudang sampai dia jalan keluar cari sinyal.
//
// Dengan catatan ini aplikasi tetap bisa dibuka: identitasnya diingat, halaman hitung
// jalan dari cache, simpanan masuk antrian seperti biasa.
//
// Yang ditulis di sini SENGAJA cuma id + email. TIDAK ada token apa pun -- token tetap
// dipegang @supabase/auth-js di penyimpanannya sendiri. Jadi "sesi lokal" tidak memberi
// akses sedikit pun ke server: begitu menyentuh jaringan, RLS tetap menuntut token asli.
// Nilainya murni supaya antarmuka tahu "ini siapa" tanpa bertanya ke server.

const KEY = 'so-sesi-v1'

export function simpanSesiLokal(session, store = globalThis.localStorage) {
  const id = session?.user?.id
  const email = session?.user?.email
  if (!id || !email) return false
  try {
    store?.setItem(KEY, JSON.stringify({ id, email }))
    return true
  } catch {
    // Kuota penuh / mode privat. Tidak fatal: cuma berarti reload offline nanti
    // tetap minta login, sama seperti sebelum ada fitur ini.
    return false
  }
}

// Kembalikan bentuk yang menyerupai session Supabase supaya halaman-halaman yang
// membaca `session.user.id` / `session.user.email` tidak perlu tahu bedanya. Penanda
// `lokal: true` dipakai untuk mematikan jalur yang memang butuh server.
export function bacaSesiLokal(store = globalThis.localStorage) {
  try {
    const isi = JSON.parse(store?.getItem(KEY) || 'null')
    if (!isi || !isi.id || !isi.email) return null
    return { user: { id: isi.id, email: isi.email }, lokal: true }
  } catch {
    return null
  }
}

export function hapusSesiLokal(store = globalThis.localStorage) {
  try { store?.removeItem(KEY) } catch { /* diblokir: tidak ada yang bisa dilakukan */ }
}

// Keputusan "layar mana yang ditampilkan" saat boot atau saat auth-js berteriak
// SIGNED_OUT. Dipisah dari App.jsx supaya bisa diuji tanpa DOM -- ini logika yang
// paling gampang salah, dan salahnya mahal: keliru ke arah satu, karyawan ditendang
// ke login di tengah gudang; keliru ke arah lain, akun yang sudah dinonaktifkan admin
// tetap bisa membuka aplikasi.
//
//   sesiServer ada  -> pakai itu (satu-satunya yang punya token sah)
//   tidak ada       -> pakai identitas tersimpan, kalau pernah login di HP ini
//   dua-duanya nihil-> halaman Login
export function pilihSesi(sesiServer, tersimpan) {
  return sesiServer || tersimpan || null
}

// Sesi asli gagal dipulihkan -- ini logout sungguhan atau cuma sinyal belum balik?
// Cuma kegagalan yang BUKAN soal jaringan (refresh token dicabut, akun dinonaktifkan)
// yang boleh memulangkan karyawan ke halaman login.
export function logoutSungguhan(error, cekJaringan) {
  if (!error) return false
  return !cekJaringan(error)
}

// ── Sesi milik @supabase/auth-js ────────────────────────────────────────────
// Nama slot localStorage tempat auth-js menyimpan sesinya. Rumusnya sama persis
// dengan bawaan supabase-js (`sb-<subdomain>-auth-token`); sengaja TIDAK ditimpa
// lewat opsi `storageKey`, karena mengganti nama slot berarti seluruh karyawan yang
// sudah login harus login ulang sekali.
export function kunciSesiServer(url) {
  try {
    return `sb-${new URL(url).hostname.split('.')[0]}-auth-token`
  } catch {
    return null
  }
}

// Buang sesi Supabase dari HP secara paksa.
//
// `signOut()` TIDAK selalu melakukannya. Kalau access token sudah kedaluwarsa DAN
// sinyal tidak ada, auth-js berhenti di awal dengan galat jaringan dan slotnya
// dibiarkan utuh. Akibatnya karyawan yang menekan Keluar di gudang akan masuk sendiri
// lagi begitu ponselnya dapat sinyal -- refresh token lama masih di sana. Jadi tombol
// Keluar selalu menutup `signOut()` dengan fungsi ini.
export function lupakanSesiServer(url, store = globalThis.localStorage) {
  const key = kunciSesiServer(url)
  if (!key) return false
  try {
    store?.removeItem(key)
    store?.removeItem(`${key}-code-verifier`)
    return true
  } catch {
    return false
  }
}
