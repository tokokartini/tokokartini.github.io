// Antrian kiriman yang belum sampai ke server, disimpan di localStorage.
//
// Tanpa ini, karyawan yang menekan Simpan di gudang bersinyal tipis kehilangan
// hitungannya begitu permintaan ke Supabase gagal — satu-satunya celah di aplikasi
// ini yang benar-benar MEMBUANG data. Sekarang entri yang gagal terkirim mendarat
// di sini dulu, tetap kelihatan di daftar "Hasil rak ini", dan dikirim ulang
// otomatis begitu sinyal balik.
//
// Isinya sengaja cuma entri stock opname (`count_entries`). Antrian bukan gudang
// data: satu entri = satu produk di satu rak milik satu orang, sama seperti indeks
// unik di DB, jadi menyimpan ulang produk yang sama MENIMPA barisnya di antrian
// (bukan menumpuk) — persis seperti perilaku "satu entri terbuka per produk".

const KEY = 'so-outbox-v1'

// Penanda id lokal. Baris antrian ikut tampil di daftar bersama baris DB, jadi
// idnya harus bisa dibedakan tanpa menebak-nebak bentuk UUID.
export const AWALAN_LOKAL = 'lokal:'

export function idLokal(pembangkit = globalThis.crypto) {
  const acak = pembangkit?.randomUUID ? pembangkit.randomUUID() : `${Math.random()}`.slice(2)
  return `${AWALAN_LOKAL}${acak}`
}

export function adalahLokal(id) {
  return typeof id === 'string' && id.startsWith(AWALAN_LOKAL)
}

export function bacaOutbox(store = globalThis.localStorage) {
  try {
    const raw = store?.getItem(KEY)
    if (!raw) return []
    const list = JSON.parse(raw)
    return Array.isArray(list) ? list.filter((it) => it && it.id && it.product_name) : []
  } catch {
    // JSON rusak / localStorage diblokir (mode privat) — anggap antrian kosong.
    return []
  }
}

export function tulisOutbox(list, store = globalThis.localStorage) {
  try {
    store?.setItem(KEY, JSON.stringify(list))
    return true
  } catch {
    // Kuota penuh: kembalikan false supaya pemanggil TIDAK menelan error diam-diam.
    // Di sini kegagalan berarti data benar-benar hilang, beda dengan productCache.
    return false
  }
}

// Masukkan/timpa satu entri. Kunci timpa = rak + pemilik + nama produk, sama
// dengan indeks unik `count_entries`. Mengembalikan { list, item }.
export function antre(item, store = globalThis.localStorage) {
  const isi = { ...item, id: item.id || idLokal() }
  const lama = bacaOutbox(store)
  const list = lama.filter(
    (it) =>
      !(it.rack === isi.rack && it.user_id === isi.user_id && it.product_name === isi.product_name),
  )
  list.push(isi)
  return { list, item: isi, tersimpan: tulisOutbox(list, store) }
}

export function buangOutbox(id, store = globalThis.localStorage) {
  const list = bacaOutbox(store).filter((it) => it.id !== id)
  tulisOutbox(list, store)
  return list
}

export function outboxRak(list, rack, uid) {
  return list.filter((it) => it.rack === rack && it.user_id === uid)
}

// Apakah kegagalan ini karena jaringan (layak diantre & dicoba lagi), atau
// karena servernya menolak (harus dilaporkan, mengulang cuma bikin antrian macet)?
//
// Supabase mengembalikan objek error, bukan melempar, untuk penolakan API — yang
// itu selalu punya `code`. Kegagalan fetch tidak punya `code` dan pesannya berbeda
// tiap browser, jadi dicocokkan lewat daftar di bawah.
const POLA_JARINGAN = /failed to fetch|networkerror|network request failed|load failed|timeout|aborted|fetch failed/i

// Sinyal tipis di gudang jarang gagal cepat — permintaannya menggantung. Tanpa
// batas waktu, karyawan menatap tombol "Menyimpan..." sampai menyerah dan menutup
// aplikasi, dan hitungannya tidak pernah masuk antrian. Lewat batas ini kita
// anggap saja putus dan diantre.
//
// Permintaan yang telanjur mendarat di server tidak jadi masalah: pengiriman ulang
// dari antrian menimpa baris yang sama (kunci unik rak+produk+pemilik), bukan
// membuat entri kedua.
export const BATAS_MS = 10000

export function denganBatasWaktu(promise, ms = BATAS_MS, timer = globalThis.setTimeout) {
  return new Promise((resolve, reject) => {
    const id = timer(() => reject(new Error('timeout: server tidak menjawab')), ms)
    Promise.resolve(promise).then(
      (v) => { globalThis.clearTimeout?.(id); resolve(v) },
      (e) => { globalThis.clearTimeout?.(id); reject(e) },
    )
  })
}

export function gagalJaringan(err, nav = globalThis.navigator) {
  if (nav && nav.onLine === false) return true
  if (!err) return false
  if (err.code) return false
  const pesan = `${err.message || err.name || err}`
  return POLA_JARINGAN.test(pesan)
}
