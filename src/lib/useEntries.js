import { useCallback, useEffect, useState } from 'react'
import { supabase } from './supabase'
import { totalQty } from './convert'

export function useEntries(rack, session) {
  const [entries, setEntries] = useState([])

  const refresh = useCallback(async () => {
    const { data } = await supabase
      .from('count_entries')
      .select('*')
      .eq('rack', rack)
      .order('updated_at', { ascending: false })
      .limit(300)
    setEntries(data || [])
  }, [rack])

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
      ;({ error } = await supabase.from('count_entries').update(payload).eq('id', existingId).is('uploaded_at', null))
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

  return { entries, saveEntry, refresh }
}
