# Desain: Hapus Entri di "Hasil rak ini" — SO Kartini

Tanggal: 2026-07-29
Status: disetujui Sopian (sesi 2026-07-29)

## Masalah

Karyawan menghitung sebuah produk di Rak 3, lalu sadar produk itu sudah dihitung di rak lain sebelumnya. Entri di Rak 3 jadi salah masuk. Saat ini satu-satunya cara "membatalkannya" adalah mengubah qty jadi 0 — barisnya tetap nongkrong di daftar dan tetap ikut ter-upload sebagai baris qty 0. Produk yang sama muncul di beberapa rak adalah hal biasa di toko ini, jadi kasus ini sering terjadi.

Selain itu, saat ini **tidak ada cara sama sekali** menghapus entri lewat web: tabel `count_entries` tidak punya policy `delete`, jadi bahkan admin pun harus lewat Supabase Dashboard.

## Keputusan produk

- Tombol hapus ada di kartu **"Hasil rak ini"** pada halaman hitung karyawan.
- **Hapus betulan**, bukan sekadar menyembunyikan: datanya dibuang sehingga tidak ikut ter-upload. Menyembunyikan saja justru mempertahankan masalah dobel hitung yang mau dihindari.
- **Hanya entri yang belum di-upload.** Kartu itu memang sudah menyaring `uploaded_at` null (`Count.jsx:29`), jadi semua yang terlihat aman dihapus — belum ada salinannya di spreadsheet. Entri terupload tetap terkunci dan tidak bisa dihapus siapa pun lewat app, supaya tidak ada baris yatim di tab Log.
- **Siapa pun boleh** menghapus entri terbuka di rak yang sedang dibuka, menyamai aturan edit yang sudah berlaku (`schema.sql:49-50` mengizinkan semua authenticated mengubah entri terbuka). Membolehkan edit tapi melarang hapus akan terasa janggal.

## Rancangan

### Database

Policy baru di `count_entries` (satu-satunya perubahan skema):

```sql
create policy "delete open entries" on count_entries
  for delete to authenticated using (uploaded_at is null);
```

Batas `uploaded_at is null` inilah penjaga sebenarnya — bukan tampilan. Walau seseorang memanggil API langsung, entri terupload tetap tidak bisa dihapus.

### Aplikasi

- `useEntries` mendapat `deleteEntry(id)`: `delete().eq('id', id).is('uploaded_at', null).select('id')`. Bila tidak ada baris terhapus → lempar pesan "Entri sudah terkunci (terupload) — tidak bisa dihapus", pola sama seperti `saveEntry` (`useEntries.js:37-40`).
- `Count.jsx`: tiap baris di "Hasil rak ini" dapat tombol hapus di sisi kanan bersama angka qty. Konfirmasi menyebut nama produk dan raknya. `stopPropagation` supaya klik tombol tidak ikut membuka form edit.
- CSS: satu pembungkus flex untuk qty + tombol, dan gaya tombol hapus (merah, tanpa latar). Ukuran sentuh dilebihkan supaya tidak salah tekan di HP.

## Testing

Tidak ada unit test — `deleteEntry` menyentuh Supabase, dan proyek ini hanya punya test fungsi murni. Diverifikasi lewat smoke test terhadap Supabase live memakai kunci anon + login karyawan (bukan service key), supaya yang teruji benar-benar policy RLS-nya:

1. Login `tes`, sisipkan satu entri, hapus lewat client → terhapus.
2. Sisipkan entri lain, tandai `uploaded_at` lewat service key, coba hapus sebagai `tes` → **tidak** terhapus.
3. Bersihkan sisa data; pastikan `count_entries` kembali kosong.

## Di luar cakupan

- Menghapus entri yang sudah di-upload (dan baris pasangannya di tab Log).
- Membuka kunci entri terupload supaya bisa diedit ulang.
- Membatasi hapus hanya untuk entri buatan sendiri.
