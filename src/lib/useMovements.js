import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'
import { adalahLokal, denganBatasWaktu, gagalJaringan } from './antrian'
import {
  antreMutasi,
  bacaOutboxMutasi,
  buangOutboxMutasi,
  outboxSuratJalan,
} from './outboxMutasi'
import { bacaMutasiCache, tulisMutasiCache } from './movementCache'

// Baris surat jalan yang sedang disusun. Sama seperti SO, tiap Simpan langsung
// menulis ke DB -- bukan ditahan di memori sampai tombol Kirim. Kalau ditahan,
// aplikasi tertutup di tengah bongkar muat berarti seluruh surat jalan hilang.
//
// Yang gagal karena sinyal masuk antrian localStorage dan dikirim ulang sendiri,
// persis seperti alur stock opname.
export function useMovements(from, to, session) {
  const [items, setItems] = useState([])
  const [pending, setPending] = useState([])
  const [antrianMsg, setAntrianMsg] = useState('')
  const uid = session.user.id
  const username = session.user.email.split('@')[0]
  // Sesi lokal = aplikasi dibuka tanpa sinyal dengan token yang sudah kedaluwarsa
  // (lihat `sesiLokal.js`). Tidak ada token sah, jadi setiap panggilan pasti ditolak
  // dengan galat ber-`code` -- yang oleh `gagalJaringan()` dianggap "server menolak"
  // dan bikin ketikan dilaporkan gagal alih-alih diantre. Di mode ini jaringan tidak
  // disentuh sama sekali.
  const tanpaSinyal = !!session.lokal

  const muatPending = useCallback(() => {
    const list = outboxSuratJalan(bacaOutboxMutasi(), from, to, uid)
    setPending(list)
    return list
  }, [from, to, uid])

  const refresh = useCallback(async () => {
    if (!from || !to) {
      setItems([])
      return []
    }
    if (tanpaSinyal) {
      const cache = bacaMutasiCache(from, to, uid)
      setItems(cache)
      return cache
    }
    const { data, error } = await supabase
      .from('movements')
      .select('*')
      .eq('from_loc', from)
      .eq('to_loc', to)
      .eq('user_id', uid)
      .is('uploaded_at', null)
      .order('updated_at', { ascending: false })
      .limit(300)
    if (error) {
      // Server tak terjangkau padahal sesi masih sah (sinyal baru saja putus).
      // Jangan kosongkan daftar -- pakai salinan terakhir, supaya karyawan tidak
      // mengira surat jalannya lenyap.
      const cache = bacaMutasiCache(from, to, uid)
      if (cache.length) setItems(cache)
      return null
    }
    const rows = data || []
    setItems(rows)
    tulisMutasiCache(from, to, uid, rows)
    return rows
  }, [from, to, uid, tanpaSinyal])

  // Kirim satu baris antrian ke server.
  //
  // `timpaKonflik` cuma dinyalakan saat mengosongkan antrian: di sana baris memang
  // lebih baru daripada yang sudah ada, dan menolaknya berarti membuang ketikan yang
  // tidak bisa diulang. Di jalur simpan biasa bentrok tetap dilaporkan supaya petugas
  // membuka baris yang ada dan tidak diam-diam menimpa angka sebelumnya.
  const kirimSatu = useCallback(async (item, { timpaKonflik = false } = {}) => {
    const payload = {
      units: item.units,
      qty_total: item.qty_total,
      nota: item.nota,
      username: item.username,
      updated_at: item.updated_at,
    }

    if (item.server_id) {
      const { data, error } = await denganBatasWaktu(
        supabase
          .from('movements')
          .update(payload)
          .eq('id', item.server_id)
          .is('uploaded_at', null)
          .select('id'),
      )
      if (error) throw error
      if (data && data.length) return {}
      return { hilang: true }
    }

    const { error } = await denganBatasWaktu(
      supabase.from('movements').insert({
        ...payload,
        user_id: item.user_id,
        jenis: item.jenis,
        from_loc: item.from_loc,
        to_loc: item.to_loc,
        product_name: item.product_name,
      }),
    )
    if (!error) return {}
    if (error.code !== '23505') throw error
    if (!timpaKonflik) return { bentrok: true }

    const { data: ada, error: cariErr } = await supabase
      .from('movements')
      .select('id')
      .eq('from_loc', item.from_loc)
      .eq('to_loc', item.to_loc)
      .eq('user_id', item.user_id)
      .eq('product_name', item.product_name)
      .is('uploaded_at', null)
      .limit(1)
    if (cariErr) throw cariErr
    if (!ada || !ada.length) return { hilang: true }

    const { error: updErr } = await supabase
      .from('movements')
      .update(payload)
      .eq('id', ada[0].id)
      .is('uploaded_at', null)
    if (updErr) throw updErr
    return { ditimpa: true }
  }, [])

  // Kosongkan antrian. Berhenti begitu ketemu kegagalan jaringan lagi -- sisanya
  // menunggu percobaan berikutnya, urutannya tetap terjaga.
  //
  // Yang dikirim SELURUH antrian milik orang ini, bukan cuma surat jalan yang sedang
  // dibuka: baris yang tertahan di pasangan lokasi lain tidak akan pernah terkirim
  // kalau disaring per surat jalan. Tiap baris sudah membawa lokasinya sendiri.
  const kirimAntrian = useCallback(async () => {
    if (tanpaSinyal) {
      const sisa = outboxSuratJalan(bacaOutboxMutasi(), from, to, uid).length
      return { sisa, terkirim: 0, catatan: [] }
    }
    const antrian = bacaOutboxMutasi().filter((it) => it.user_id === uid)
    if (!antrian.length) {
      setAntrianMsg('')
      return { sisa: 0, terkirim: 0, catatan: [] }
    }
    let terkirim = 0
    const catatan = []
    for (const item of antrian) {
      try {
        const hasil = await kirimSatu(item, { timpaKonflik: true })
        if (hasil.hilang) {
          catatan.push(
            `${item.product_name}: barisnya di pusat sudah terkirim/terhapus, ${item.qty_total} TIDAK jadi ditulis — catat ulang kalau perlu`,
          )
        } else if (hasil.ditimpa) {
          catatan.push(`${item.product_name}: baris lama ditimpa angka terbaru (${item.qty_total})`)
        }
        buangOutboxMutasi(item.id)
        terkirim++
      } catch (err) {
        if (gagalJaringan(err)) break
        // Ditolak server, bukan soal sinyal. Kalau dicoba terus, antrian macet dan
        // baris di belakangnya ikut tertahan -- jadi dibuang, TAPI angkanya disebut
        // supaya masih bisa diketik ulang.
        catatan.push(
          `${item.product_name}: ditolak pusat (${err.message || err.code}) — ${item.qty_total} harus dicatat ulang`,
        )
        buangOutboxMutasi(item.id)
      }
    }
    const sisa = muatPending().length
    setAntrianMsg(catatan.join(' · '))
    if (terkirim) await refresh()
    return { sisa, terkirim, catatan }
  }, [from, to, uid, tanpaSinyal, kirimSatu, muatPending, refresh])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => { muatPending() }, [muatPending])

  useEffect(() => {
    kirimAntrian()
    const balikSinyal = () => { kirimAntrian() }
    window.addEventListener('online', balikSinyal)
    return () => window.removeEventListener('online', balikSinyal)
  }, [kirimAntrian])

  async function saveItem(group, units, jenis, nota, existingId) {
    const qty_total = totalQty(units)
    if (qty_total <= 0) throw new Error('Jumlahnya masih 0 — isi dulu berapa yang dipindah')

    const lokal = adalahLokal(existingId)
    const sebelumnya = lokal ? pending.find((p) => p.id === existingId) : null
    const item = {
      id: lokal ? existingId : undefined,
      from_loc: from,
      to_loc: to,
      user_id: uid,
      jenis,
      product_name: group.name,
      // Baris antrian bisa berupa perubahan atas baris yang SUDAH ada di server
      // (diedit saat offline) -- id barisnya ikut dibawa supaya nanti di-update,
      // bukan di-insert jadi baris kedua.
      server_id: lokal ? (sebelumnya?.server_id ?? null) : (existingId || null),
      units,
      qty_total,
      nota: nota || '',
      username,
      updated_at: new Date().toISOString(),
    }

    if (tanpaSinyal) {
      const { tersimpan } = antreMutasi(item)
      muatPending()
      if (!tersimpan) {
        throw new Error('Simpanan HP penuh — barang ini TIDAK tersimpan. Catat di kertas dulu.')
      }
      setAntrianMsg('')
      return { antre: true }
    }

    let hasil
    try {
      hasil = await kirimSatu(item)
    } catch (err) {
      if (!gagalJaringan(err)) {
        await refresh()
        if (err.code === '23505') throw new Error('Barang ini sudah ada di surat jalan — buka dari daftar')
        throw new Error('Gagal simpan — cek sinyal, lalu coba lagi')
      }
      const { tersimpan } = antreMutasi(item)
      muatPending()
      if (!tersimpan) {
        throw new Error('Sinyal putus DAN simpanan HP penuh — barang ini TIDAK tersimpan. Catat di kertas dulu.')
      }
      setAntrianMsg('')
      return { antre: true }
    }

    if (hasil.bentrok) {
      await refresh()
      throw new Error('Barang ini sudah ada di surat jalan — buka dari daftar')
    }
    if (hasil.hilang) {
      const rows = await refresh()
      if (lokal) { buangOutboxMutasi(existingId); muatPending() }
      if (rows && item.server_id && !rows.find((r) => r.id === item.server_id)) {
        throw new Error('Barang ini sudah terkirim atau dihapus — cek lagi daftarnya')
      }
      throw new Error('Barang ini sudah tidak bisa diubah — cek lagi daftarnya')
    }

    if (lokal) { buangOutboxMutasi(existingId); muatPending() }
    await refresh()
    return { antre: false }
  }

  async function deleteItem(id) {
    // Baris antrian: buang dulu dari antrian supaya angkanya tidak terkirim
    // belakangan. Kalau baris itu ternyata perubahan atas baris yang SUDAH ada di
    // server, aslinya tetap harus dihapus -- lanjut ke jalur biasa dengan id
    // servernya. Hapus yang gagal tidak pernah menghilangkan ketikan, jadi tidak
    // perlu ikut diantre.
    if (adalahLokal(id)) {
      const item = pending.find((p) => p.id === id)
      if (tanpaSinyal && item?.server_id) {
        // Baris ini menimpa yang SUDAH ada di server. Membuangnya sekarang cuma
        // menghapus perubahan offline-nya -- baris aslinya tetap hidup di pusat dan
        // tetap ikut terkirim, padahal petugas sudah yakin barangnya dicoret.
        throw new Error('Belum ada sinyal — barang lama baru bisa dihapus setelah tersambung')
      }
      buangOutboxMutasi(id)
      muatPending()
      if (!item?.server_id) return
      id = item.server_id
    }
    if (tanpaSinyal) {
      throw new Error('Belum ada sinyal — barang lama baru bisa dihapus setelah tersambung')
    }
    const { data, error } = await supabase
      .from('movements')
      .delete()
      .eq('id', id)
      .is('uploaded_at', null)
      .select('id')
    if (error) {
      await refresh()
      throw new Error('Gagal hapus — cek sinyal, lalu coba lagi')
    }
    if (!data || data.length === 0) {
      await refresh()
      throw new Error('Barang ini sudah terkirim atau dihapus — cek lagi daftarnya')
    }
    await refresh()
  }

  return { items, pending, antrianMsg, saveItem, deleteItem, refresh, kirimAntrian }
}
