// Mesin antrian kiriman yang belum sampai ke server, disimpan di localStorage.
//
// Tanpa ini, karyawan yang menekan Simpan di gudang bersinyal tipis kehilangan
// ketikannya begitu permintaan ke Supabase gagal -- satu-satunya celah di aplikasi
// ini yang benar-benar MEMBUANG data. Yang gagal terkirim mendarat di sini dulu,
// tetap kelihatan di daftar, dan dikirim ulang otomatis begitu sinyal balik.
//
// Ada dua antrian yang bentuknya sama tapi kunci timpanya beda: stock opname
// (rak + pemilik + produk) dan surat jalan (asal + tujuan + pemilik + produk).
// Keduanya dibuat dari pabrik yang sama supaya aturannya tidak pernah berbeda --
// pernah ada dua salinan, dan salinan selalu berakhir tidak sinkron.

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

// `kunciSama(a, b)` menentukan kapan satu entri MENIMPA entri lain di antrian --
// harus sama persis dengan indeks unik tabelnya di DB, kalau tidak pengiriman ulang
// bikin baris kedua alih-alih memperbarui yang pertama.
export function buatAntrian({ key, kunciSama, sah = (it) => it && it.id && it.product_name }) {
  function baca(store = globalThis.localStorage) {
    try {
      const raw = store?.getItem(key)
      if (!raw) return []
      const list = JSON.parse(raw)
      return Array.isArray(list) ? list.filter(sah) : []
    } catch {
      // JSON rusak / localStorage diblokir (mode privat) -- anggap antrian kosong.
      return []
    }
  }

  function tulis(list, store = globalThis.localStorage) {
    try {
      store?.setItem(key, JSON.stringify(list))
      return true
    } catch {
      // Kuota penuh: kembalikan false supaya pemanggil TIDAK menelan error diam-diam.
      // Di sini kegagalan berarti data benar-benar hilang, beda dengan productCache.
      return false
    }
  }

  // Masukkan/timpa satu entri. Mengembalikan { list, item, tersimpan }.
  function antre(item, store = globalThis.localStorage) {
    const isi = { ...item, id: item.id || idLokal() }
    const list = baca(store).filter((it) => !kunciSama(it, isi))
    list.push(isi)
    return { list, item: isi, tersimpan: tulis(list, store) }
  }

  function buang(id, store = globalThis.localStorage) {
    const list = baca(store).filter((it) => it.id !== id)
    tulis(list, store)
    return list
  }

  return { KEY: key, baca, tulis, antre, buang }
}

// Apakah kegagalan ini karena jaringan (layak diantre & dicoba lagi), atau
// karena servernya menolak (harus dilaporkan, mengulang cuma bikin antrian macet)?
//
// Supabase mengembalikan objek error, bukan melempar, untuk penolakan API -- yang
// itu selalu punya `code`. Kegagalan fetch tidak punya `code` dan pesannya berbeda
// tiap browser, jadi dicocokkan lewat daftar di bawah.
const POLA_JARINGAN = /failed to fetch|networkerror|network request failed|load failed|timeout|aborted|fetch failed/i

// Sinyal tipis di gudang jarang gagal cepat -- permintaannya menggantung. Tanpa
// batas waktu, karyawan menatap tombol "Menyimpan..." sampai menyerah dan menutup
// aplikasi, dan ketikannya tidak pernah masuk antrian.
//
// Permintaan yang telanjur mendarat di server tidak jadi masalah: pengiriman ulang
// dari antrian menimpa baris yang sama (kunci uniknya), bukan membuat entri kedua.
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
