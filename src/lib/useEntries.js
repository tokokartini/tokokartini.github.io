import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'

export function useEntries(rack, session) {
  const [entries, setEntries] = useState([])
  const uid = session.user.id

  const refresh = useCallback(async () => {
    const { data, error } = await supabase
      .from('count_entries')
      .select('*')
      .eq('rack', rack)
      .eq('user_id', uid)
      .order('updated_at', { ascending: false })
      .limit(300)
    if (error) return null
    setEntries(data || [])
    return data || []
  }, [rack, uid])

  useEffect(() => { refresh() }, [refresh])

  async function saveEntry(group, units, expired, existingId) {
    const payload = {
      units,
      qty_total: totalQty(units),
      expired_date: expired || null,
      username: session.user.email.split('@')[0],
      updated_at: new Date().toISOString(),
    }
    let error
    if (existingId) {
      const { data, error: updErr } = await supabase
        .from('count_entries')
        .update(payload)
        .eq('id', existingId)
        .is('uploaded_at', null)
        .select('id')
      error = updErr
      if (!error && (!data || data.length === 0)) {
        const rows = await refresh()
        if (rows) {
          const found = rows.find((r) => r.id === existingId)
          if (!found) throw new Error('Entri sudah dihapus dari daftar — cek lagi daftarnya')
          if (found.uploaded_at) throw new Error('Entri sudah terkunci (terupload) — hubungi admin')
        }
        throw new Error('Entri sudah tidak bisa diubah — mungkin sudah di-upload atau dihapus. Cek daftarnya.')
      }
    } else {
      ;({ error } = await supabase.from('count_entries').insert({
        ...payload,
        user_id: session.user.id,
        rack,
        product_name: group.name,
      }))
    }
    if (error) {
      await refresh()
      if (error.code === '23505') throw new Error('Sudah ada entri produk ini — buka dari daftar')
      throw new Error('Gagal simpan — cek sinyal, lalu coba lagi')
    }
    await refresh()
  }

  async function deleteEntry(id) {
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

  return { entries, saveEntry, deleteEntry, refresh }
}
