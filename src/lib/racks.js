// Daftar lokasi (tabel `racks`), dengan salinan di HP.
//
// Tanpa salinan ini, membuka aplikasi tanpa sinyal berhenti di "Memuat daftar
// lokasi..." -- karyawan tidak bisa masuk ke halaman hitung maupun surat jalan sama
// sekali, jadi antrian offline pun tidak ada gunanya. Lokasi jarang berubah
// (terakhir 2026-08-04) dan tetap disegarkan tiap kali sinyal ada.

import { useEffect, useState } from 'react'
import { supabase } from './supabase'

const KEY = 'so-racks-v1'

export function bacaRakTersimpan(store = globalThis.localStorage) {
  try {
    const list = JSON.parse(store?.getItem(KEY) || 'null')
    return Array.isArray(list) ? list.filter((r) => typeof r === 'string') : []
  } catch {
    return []
  }
}

export function tulisRakTersimpan(names, store = globalThis.localStorage) {
  try {
    store?.setItem(KEY, JSON.stringify(names))
    return true
  } catch {
    return false
  }
}

export function useRacks() {
  const [racks, setRacks] = useState(bacaRakTersimpan)

  useEffect(() => {
    let batal = false
    supabase
      .from('racks')
      .select('name')
      .eq('active', true)
      .order('sort')
      .then(({ data, error }) => {
        // Gagal ke server: pertahankan daftar tersimpan, jangan dikosongkan.
        if (batal || error || !data) return
        const names = data.map((r) => r.name)
        if (!names.length) return
        setRacks(names)
        tulisRakTersimpan(names)
      })
    return () => { batal = true }
  }, [])

  return racks
}
