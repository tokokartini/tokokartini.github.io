import { useEffect, useState } from 'react'
import { supabase } from './supabase'
import { groupProducts } from './groupProducts'
import { bacaCache, tulisCache, cacheMasihSah, PRODUCT_COLUMNS } from './productCache'

// Daftar produk siap pakai (sudah dikelompokkan per nama produk), dengan cache
// localStorage. Dipakai halaman Hitung maupun halaman Pengeluaran -- disatukan di
// sini supaya keduanya tidak pernah punya aturan cache yang berbeda.
//
// Cache lebih dulu supaya layar langsung terisi, lalu cek ke server apakah cache
// masih sama. Kalau sama, ~2772 baris tidak diunduh sama sekali -- cukup dua
// permintaan kecil (penanda sync + jumlah produk).
export function useProducts() {
  const [groups, setGroups] = useState([])
  const [produkMsg, setProdukMsg] = useState('')

  useEffect(() => {
    let batal = false

    async function unduhSemua() {
      let all = []
      for (let offset = 0; ; offset += 1000) {
        const { data, error } = await supabase
          .from('products').select(PRODUCT_COLUMNS).eq('active', true)
          .range(offset, offset + 999)
        if (error) throw error
        all = all.concat(data || [])
        if ((data || []).length < 1000) return all
      }
    }

    async function penandaServer() {
      const [sync, jml] = await Promise.all([
        supabase.from('sync_runs').select('ran_at').eq('ok', true)
          .order('ran_at', { ascending: false }).limit(1),
        supabase.from('products').select('sku', { count: 'exact', head: true }).eq('active', true),
      ])
      if (sync.error || jml.error) throw sync.error || jml.error
      return { stamp: sync.data?.[0]?.ran_at ?? null, count: jml.count }
    }

    async function load() {
      const cache = bacaCache()
      if (cache && !batal) {
        setGroups(groupProducts(cache.products))
        setProdukMsg('')
      }
      try {
        const fresh = await penandaServer()
        if (batal) return
        if (cacheMasihSah(cache, fresh)) return
        const all = await unduhSemua()
        if (batal) return
        setGroups(groupProducts(all))
        tulisCache(fresh.stamp, all)
        setProdukMsg('')
      } catch {
        // Gagal ke server: kalau cache ada, pekerjaan tetap jalan pakai daftar lama.
        if (batal) return
        setProdukMsg(
          cache
            ? 'Daftar produk dari simpanan HP — sinyal sedang bermasalah, produk baru mungkin belum ada.'
            : 'Gagal memuat daftar produk — cek sinyal, lalu muat ulang halaman.',
        )
      }
    }

    load()
    return () => { batal = true }
  }, [])

  return { groups, produkMsg }
}
