import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'

// Baris surat jalan yang sedang disusun. Sama seperti SO, tiap Simpan langsung
// menulis ke DB -- bukan ditahan di memori sampai tombol Kirim. Kalau ditahan,
// aplikasi tertutup di tengah bongkar muat berarti seluruh surat jalan hilang.
export function useMovements(from, to, session) {
  const [items, setItems] = useState([])
  const uid = session.user.id

  const refresh = useCallback(async () => {
    if (!from || !to) {
      setItems([])
      return []
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
    if (error) return null
    setItems(data || [])
    return data || []
  }, [from, to, uid])

  useEffect(() => { refresh() }, [refresh])

  async function saveItem(group, units, jenis, nota, existingId) {
    const qty_total = totalQty(units)
    if (qty_total <= 0) throw new Error('Jumlahnya masih 0 — isi dulu berapa yang dipindah')

    const payload = {
      units,
      qty_total,
      nota: nota || '',
      username: session.user.email.split('@')[0],
      updated_at: new Date().toISOString(),
    }

    let error
    if (existingId) {
      const { data, error: updErr } = await supabase
        .from('movements')
        .update(payload)
        .eq('id', existingId)
        .is('uploaded_at', null)
        .select('id')
      error = updErr
      if (!error && (!data || data.length === 0)) {
        // Baris menghilang di antara render dan Simpan -- hampir selalu karena
        // surat jalan sudah terkirim dari HP lain. Muat ulang supaya daftarnya
        // jujur, lalu jelaskan sebabnya, bukan cuma "gagal".
        const rows = await refresh()
        if (rows && !rows.find((r) => r.id === existingId)) {
          throw new Error('Barang ini sudah terkirim atau dihapus — cek lagi daftarnya')
        }
        throw new Error('Barang ini sudah tidak bisa diubah — cek lagi daftarnya')
      }
    } else {
      ;({ error } = await supabase.from('movements').insert({
        ...payload,
        user_id: uid,
        jenis,
        from_loc: from,
        to_loc: to,
        product_name: group.name,
      }))
    }

    if (error) {
      await refresh()
      if (error.code === '23505') throw new Error('Barang ini sudah ada di surat jalan — buka dari daftar')
      throw new Error('Gagal simpan — cek sinyal, lalu coba lagi')
    }
    await refresh()
  }

  async function deleteItem(id) {
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

  return { items, saveItem, deleteItem, refresh }
}
