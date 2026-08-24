// Antrian surat jalan: baris mutasi yang belum sampai ke server.
//
// Mesinnya sama dengan antrian stock opname (`antrian.js`), yang beda cuma kunci
// timpanya: `movements` unik per asal + tujuan + pemilik + produk, bukan per rak.
// Satu produk bisa muncul di dua surat jalan sekaligus (mis. dipindah ke display
// DAN ke gudang lain), jadi kedua sisi lokasi wajib ikut jadi kunci -- kalau cuma
// produk + pemilik, surat jalan kedua akan menimpa yang pertama di antrian.

import { buatAntrian } from './antrian'

const mutasi = buatAntrian({
  key: 'so-outbox-mutasi-v1',
  kunciSama: (a, b) =>
    a.from_loc === b.from_loc &&
    a.to_loc === b.to_loc &&
    a.user_id === b.user_id &&
    a.product_name === b.product_name,
})

export const bacaOutboxMutasi = mutasi.baca
export const tulisOutboxMutasi = mutasi.tulis
export const antreMutasi = mutasi.antre
export const buangOutboxMutasi = mutasi.buang

// Baris antrian untuk satu surat jalan yang sedang dibuka.
export function outboxSuratJalan(list, from, to, uid) {
  return list.filter((it) => it.from_loc === from && it.to_loc === to && it.user_id === uid)
}
