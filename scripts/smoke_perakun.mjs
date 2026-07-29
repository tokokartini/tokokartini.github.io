// Smoke test RLS: entri per akun (aturan "tiap karyawan cuma milik sendiri").
//
// PERINGATAN — script ini menyentuh proyek Supabase LIVE dan Google Sheet LIVE:
// - Membuat lalu menghapus dua akun sementara (zzujia, zzujib).
// - Menulis SATU baris ke tab Log ("SO Toko Kartini") lewat upload-rak — baris ini harus
//   dihapus MANUAL sesudah run (cari baris dengan kolom Rak = 'ZZ Rak Uji').
// - Rak uji sengaja dinamai mencolok ('ZZ Rak Uji'). JANGAN PERNAH mengarahkan RAK di bawah
//   ke nama rak sungguhan — data hasil run ini dibuang habis di akhir script.
// - Jalankan di luar jam SO aktif; ini bukan sandbox.
//
// Run (dari root proyek):
//   $env:SO_SERVICE_KEY = "<service_role_key dari scripts/config.local.json>"
//   node scripts/smoke_perakun.mjs
//
// Dipakai buat verifikasi ulang batas RLS sebelum mengubah schema.sql / policy count_entries.

import { createClient } from '@supabase/supabase-js'
import { ownEntriesQuery } from '../src/lib/entryQueries.js'

const URL = 'https://qfqulgkpbjceizrapyom.supabase.co'
const ANON = 'sb_publishable_HDK2-JqOPUY9lFnjZ9JZYg_GpRxOzkQ'
const SERVICE = process.env.SO_SERVICE_KEY

if (!SERVICE) {
  console.error(
    'FAIL: SO_SERVICE_KEY belum di-set.\n' +
      'Ambil service_role_key dari scripts/config.local.json, lalu jalankan:\n' +
      '  $env:SO_SERVICE_KEY = "<service_role_key>"; node scripts/smoke_perakun.mjs',
  )
  process.exit(1)
}

const log = (ok, msg) => console.log(`${ok ? 'OK  ' : 'FAIL'} ${msg}`)
const admin = createClient(URL, SERVICE)

const RAK = 'ZZ Rak Uji'
const PRODUK = 'ZZ Produk Uji Bersama'
const PRODUK_SENDIRI = 'ZZ Produk Uji Milik Sendiri'
const PASSWORD = 'UjiPerAkun2026!'

async function akun(nama) {
  const { data, error } = await admin.auth.admin.createUser({
    email: `${nama}@tokokartini.app`, password: PASSWORD, email_confirm: true,
  })
  if (error) throw new Error(`gagal bikin akun uji ${nama}: ${error.message}`)
  const c = createClient(URL, ANON)
  await c.auth.signInWithPassword({ email: `${nama}@tokokartini.app`, password: PASSWORD })
  return { id: data.user.id, c }
}

const entri = (uid, nama, produk = PRODUK) => ({
  user_id: uid, username: nama, rack: RAK, product_name: produk,
  units: [{ sku: 'ZZUJI-1', variant: 'Pcs', mult: 1, qty: 5 }], qty_total: 5,
})

const A = await akun('zzujia')
const B = await akun('zzujib')

// 1. dua orang, produk sama, rak sama -> dua-duanya boleh (indeks unik sekarang per orang)
const { data: ea, error: eaErr } = await A.c.from('count_entries').insert(entri(A.id, 'zzujia')).select('id')
const { data: eb, error: ebErr } = await B.c.from('count_entries').insert(entri(B.id, 'zzujib')).select('id')
log(!eaErr && !ebErr && ea?.length === 1 && eb?.length === 1,
  `dua entri produk sama di rak sama diterima${eaErr || ebErr ? ': ' + (eaErr || ebErr).message : ''}`)

// 2. A tidak boleh mengubah / menghapus entri B (jalur negatif)
const { data: upd } = await A.c.from('count_entries').update({ qty_total: 999 }).eq('id', eb[0].id).select('id')
log(!upd || upd.length === 0, `A ubah entri B ditolak: ${upd?.length ?? 0} baris (harus 0)`)
const { data: del } = await A.c.from('count_entries').delete().eq('id', eb[0].id).select('id')
log(!del || del.length === 0, `A hapus entri B ditolak: ${del?.length ?? 0} baris (harus 0)`)

// 3. A BOLEH mengubah dan menghapus entri MILIKNYA SENDIRI (jalur positif — memastikan
//    policy tidak kebablasan menutup akses ke entri sendiri)
const { data: ec, error: ecErr } = await A.c.from('count_entries').insert(entri(A.id, 'zzujia', PRODUK_SENDIRI)).select('id')
log(!ecErr && ec?.length === 1, `entri milik sendiri (buat uji ubah/hapus) dibuat${ecErr ? ': ' + ecErr.message : ''}`)
const idSendiri = ec?.[0]?.id
const { data: updOwn } = await A.c.from('count_entries').update({ qty_total: 777 }).eq('id', idSendiri).select('id, qty_total')
log(updOwn?.length === 1 && Number(updOwn[0].qty_total) === 777, `A ubah entri sendiri diterima: ${updOwn?.length ?? 0} baris`)
const { data: delOwn } = await A.c.from('count_entries').delete().eq('id', idSendiri).select('id')
log(delOwn?.length === 1, `A hapus entri sendiri diterima: ${delOwn?.length ?? 0} baris`)

// 4. daftar milik A hanya berisi entri A — lewat query app yang sesungguhnya
//    (src/lib/entryQueries.js, dipakai juga oleh useEntries.js), bukan query tulisan
//    ulang di test ini.
const { data: daftarA } = await ownEntriesQuery(A.c, RAK, A.id)
log(daftarA?.length === 1 && daftarA[0].id === ea[0].id, `daftar A (query app yang sama) hanya entri A: ${daftarA?.length} baris`)

// 5. upload sebagai A hanya mengklaim entri A
const { data: up, error: upErr } = await A.c.functions.invoke('upload-rak', { body: { rack: RAK } })
log(!upErr && up?.uploaded === 1, `upload A mengirim 1 entri: uploaded=${up?.uploaded} ${upErr?.message || ''}`)
const { data: cekB } = await admin.from('count_entries').select('uploaded_at').eq('id', eb[0].id)
log(cekB?.[0]?.uploaded_at === null, `entri B masih terbuka setelah A upload: ${cekB?.[0]?.uploaded_at ?? 'null'}`)

// bersihkan database + akun uji
await admin.from('count_entries').delete().in('id', [ea[0].id, eb[0].id])
await admin.auth.admin.deleteUser(A.id)
await admin.auth.admin.deleteUser(B.id)
const { data: sisa } = await admin.from('count_entries').select('id,username').eq('rack', RAK)
log((sisa?.length ?? 0) === 0, `entri uji bersih dari database: ${sisa?.length ?? 0} sisa`)

console.log(
  '\nJangan lupa: hapus manual baris tab Log dengan kolom Rak = "ZZ Rak Uji" ' +
    '(ditulis oleh upload di langkah 5) — lihat docs/superpowers/plans/2026-07-29-entri-per-akun.md Task 3 Step 5.',
)
process.exit(0)
