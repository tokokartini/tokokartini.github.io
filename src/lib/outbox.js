// Antrian stock opname: hitungan yang belum sampai ke server.
//
// Mesinnya di `antrian.js`; di sini cuma kunci penyimpanan dan aturan timpanya.
// Satu entri = satu produk di satu rak milik satu orang, sama seperti indeks unik
// `count_entries`, jadi menyimpan ulang produk yang sama MENIMPA barisnya di
// antrian (bukan menumpuk) -- persis perilaku "satu entri terbuka per produk".

import { buatAntrian } from './antrian'

export {
  AWALAN_LOKAL,
  BATAS_MS,
  adalahLokal,
  denganBatasWaktu,
  gagalJaringan,
  idLokal,
} from './antrian'

const so = buatAntrian({
  key: 'so-outbox-v1',
  kunciSama: (a, b) =>
    a.rack === b.rack && a.user_id === b.user_id && a.product_name === b.product_name,
})

export const bacaOutbox = so.baca
export const tulisOutbox = so.tulis
export const antre = so.antre
export const buangOutbox = so.buang

export function outboxRak(list, rack, uid) {
  return list.filter((it) => it.rack === rack && it.user_id === uid)
}
