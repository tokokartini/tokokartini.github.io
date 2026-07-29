// Query murni untuk count_entries — tanpa bergantung pada singleton supabase.js (yang
// membaca import.meta.env dan cuma jalan di Vite). Dipakai bareng oleh useEntries.js (di
// app) dan scripts/smoke_perakun.mjs (Node biasa), supaya smoke test benar-benar menguji
// query yang sama dipakai app, bukan tulisan ulang.

// Entri milik sendiri di satu rak (terbuka maupun sudah terupload) — dasar daftar "Hasil rak ini".
export function ownEntriesQuery(client, rack, uid) {
  return client
    .from('count_entries')
    .select('*')
    .eq('rack', rack)
    .eq('user_id', uid)
    .order('updated_at', { ascending: false })
    .limit(300)
}

// Entri terbuka milik REKAN (bukan diri sendiri) di rak yang sama — dasar peringatan
// "sudah dihitung <username>: <qty>" saat mencari/membuka produk. Read-only: kolom yang
// diambil sengaja dibatasi supaya baris ini tidak bisa dipakai untuk mengubah/menghapus.
export function othersOpenEntriesQuery(client, rack, uid) {
  return client
    .from('count_entries')
    .select('product_name, username, qty_total')
    .eq('rack', rack)
    .is('uploaded_at', null)
    .neq('user_id', uid)
}
