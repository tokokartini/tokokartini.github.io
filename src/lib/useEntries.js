import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'
import { ownEntriesQuery, othersOpenEntriesQuery } from './entryQueries'
import {
  adalahLokal,
  antre,
  bacaOutbox,
  buangOutbox,
  denganBatasWaktu,
  gagalJaringan,
  outboxRak,
} from './outbox'

export function useEntries(rack, session) {
  const [entries, setEntries] = useState([])
  const [othersOpen, setOthersOpen] = useState([])
  // Entri yang sudah diketik karyawan tapi belum sampai ke server (sinyal putus).
  const [pending, setPending] = useState([])
  const [antrianMsg, setAntrianMsg] = useState('')
  const uid = session.user.id
  const username = session.user.email.split('@')[0]

  const muatPending = useCallback(() => {
    const list = outboxRak(bacaOutbox(), rack, uid)
    setPending(list)
    return list
  }, [rack, uid])

  const refresh = useCallback(async () => {
    const [{ data, error }, { data: others, error: othersErr }] = await Promise.all([
      ownEntriesQuery(supabase, rack, uid),
      othersOpenEntriesQuery(supabase, rack, uid),
    ])
    setOthersOpen(othersErr ? [] : (others || []))
    if (error) return null
    setEntries(data || [])
    return data || []
  }, [rack, uid])

  // Kirim satu baris antrian ke server.
  //
  // `timpaKonflik` cuma dinyalakan saat mengosongkan antrian: di sana entri
  // memang lebih baru daripada baris yang sudah ada, dan menolaknya berarti
  // membuang hitungan yang tidak bisa diketik ulang. Di jalur simpan biasa
  // (online) bentrok tetap dilaporkan supaya karyawan membuka entri yang ada
  // dan tidak diam-diam menimpa hitungan sebelumnya.
  const kirimSatu = useCallback(async (item, { timpaKonflik = false } = {}) => {
    const payload = {
      units: item.units,
      qty_total: item.qty_total,
      expired_date: item.expired_date,
      username: item.username,
      updated_at: item.updated_at,
    }

    if (item.server_id) {
      const { data, error } = await denganBatasWaktu(
        supabase
          .from('count_entries')
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
      supabase.from('count_entries').insert({
        ...payload,
        user_id: item.user_id,
        rack: item.rack,
        product_name: item.product_name,
      }),
    )
    if (!error) return {}
    if (error.code !== '23505') throw error
    if (!timpaKonflik) return { bentrok: true }

    const { data: ada, error: cariErr } = await supabase
      .from('count_entries')
      .select('id')
      .eq('rack', item.rack)
      .eq('user_id', item.user_id)
      .eq('product_name', item.product_name)
      .is('uploaded_at', null)
      .limit(1)
    if (cariErr) throw cariErr
    if (!ada || !ada.length) return { hilang: true }

    const { error: updErr } = await supabase
      .from('count_entries')
      .update(payload)
      .eq('id', ada[0].id)
      .is('uploaded_at', null)
    if (updErr) throw updErr
    return { ditimpa: true }
  }, [])

  // Kosongkan antrian. Berhenti begitu ketemu kegagalan jaringan lagi — sisanya
  // menunggu percobaan berikutnya, urutannya tetap terjaga.
  //
  // Yang dikirim SELURUH antrian milik orang ini, bukan cuma rak yang sedang
  // dibuka: hitungan yang tertahan di rak lain (dihitung offline kemarin, lalu
  // aplikasi dibuka di rak berbeda) tidak akan pernah terkirim kalau disaring
  // per rak. Tiap baris sudah membawa raknya sendiri, jadi aman.
  const kirimAntrian = useCallback(async () => {
    const antrian = bacaOutbox().filter((it) => it.user_id === uid)
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
            `${item.product_name}: entri di pusat sudah terupload/terhapus, hitungan ${item.qty_total} TIDAK jadi ditulis — hitung ulang kalau perlu`,
          )
        } else if (hasil.ditimpa) {
          catatan.push(`${item.product_name}: entri lama ditimpa hitungan terbaru (${item.qty_total})`)
        }
        buangOutbox(item.id)
        terkirim++
      } catch (err) {
        if (gagalJaringan(err)) break
        // Ditolak server, bukan soal sinyal. Kalau dicoba terus, antrian macet dan
        // entri di belakangnya ikut tertahan — jadi dibuang, TAPI qty-nya disebut
        // supaya masih bisa diketik ulang.
        catatan.push(
          `${item.product_name}: ditolak pusat (${err.message || err.code}) — hitungan ${item.qty_total} harus diketik ulang`,
        )
        buangOutbox(item.id)
      }
    }
    const sisa = muatPending().length
    setAntrianMsg(catatan.join(' · '))
    if (terkirim) await refresh()
    return { sisa, terkirim, catatan }
  }, [rack, uid, kirimSatu, muatPending, refresh])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => { muatPending() }, [muatPending])

  useEffect(() => {
    kirimAntrian()
    const balikSinyal = () => { kirimAntrian() }
    window.addEventListener('online', balikSinyal)
    return () => window.removeEventListener('online', balikSinyal)
  }, [kirimAntrian])

  async function saveEntry(group, units, expired, existingId) {
    const lokal = adalahLokal(existingId)
    const sebelumnya = lokal ? pending.find((p) => p.id === existingId) : null
    const item = {
      id: lokal ? existingId : undefined,
      rack,
      user_id: uid,
      product_name: group.name,
      // Entri antrian bisa berupa perubahan atas baris yang SUDAH ada di server
      // (diedit saat offline) — id barisnya ikut dibawa supaya nanti di-update,
      // bukan di-insert jadi entri kedua.
      server_id: lokal ? (sebelumnya?.server_id ?? null) : (existingId || null),
      units,
      qty_total: totalQty(units),
      expired_date: expired || null,
      username,
      updated_at: new Date().toISOString(),
    }

    let hasil
    try {
      hasil = await kirimSatu(item)
    } catch (err) {
      if (!gagalJaringan(err)) {
        await refresh()
        if (err.code === '23505') throw new Error('Sudah ada entri produk ini — buka dari daftar')
        throw new Error('Gagal simpan — cek sinyal, lalu coba lagi')
      }
      const { tersimpan } = antre(item)
      muatPending()
      if (!tersimpan) {
        throw new Error('Sinyal putus DAN simpanan HP penuh — hitungan TIDAK tersimpan. Catat di kertas dulu.')
      }
      setAntrianMsg('')
      return { antre: true }
    }

    if (hasil.bentrok) {
      await refresh()
      throw new Error('Sudah ada entri produk ini — buka dari daftar')
    }
    if (hasil.hilang) {
      const rows = await refresh()
      if (lokal) { buangOutbox(existingId); muatPending() }
      if (rows && item.server_id) {
        const found = rows.find((r) => r.id === item.server_id)
        if (!found) throw new Error('Entri sudah dihapus dari daftar — cek lagi daftarnya')
        if (found.uploaded_at) throw new Error('Entri sudah terkunci (terupload) — hubungi admin')
      }
      throw new Error('Entri sudah tidak bisa diubah — mungkin sudah di-upload atau dihapus. Cek daftarnya.')
    }

    if (lokal) { buangOutbox(existingId); muatPending() }
    await refresh()
    return { antre: false }
  }

  async function deleteEntry(id) {
    // Baris antrian: buang dulu dari antrian supaya hitungannya tidak terkirim
    // belakangan. Kalau baris itu ternyata perubahan atas entri yang SUDAH ada di
    // server, entri aslinya tetap harus dihapus — lanjut ke jalur biasa dengan id
    // servernya. Hapus yang gagal tidak pernah menghilangkan hitungan, jadi tidak
    // perlu ikut diantre.
    if (adalahLokal(id)) {
      const item = pending.find((p) => p.id === id)
      buangOutbox(id)
      muatPending()
      if (!item?.server_id) return
      id = item.server_id
    }
    const { data, error } = await supabase
      .from('count_entries')
      .delete()
      .eq('id', id)
      .is('uploaded_at', null)
      .select('id')
    if (error) {
      await refresh()
      throw new Error('Gagal hapus — cek sinyal, lalu coba lagi')
    }
    if (!data || data.length === 0) {
      const rows = await refresh()
      if (rows) {
        const found = rows.find((r) => r.id === id)
        if (!found) throw new Error('Entri sudah dihapus dari daftar — cek lagi daftarnya')
        if (found.uploaded_at) throw new Error('Entri sudah terkunci (terupload) — tidak bisa dihapus')
      }
      throw new Error('Entri sudah tidak bisa dihapus — mungkin sudah di-upload atau dihapus. Cek daftarnya.')
    }
    await refresh()
  }

  return { entries, othersOpen, pending, antrianMsg, saveEntry, deleteEntry, refresh, kirimAntrian }
}
