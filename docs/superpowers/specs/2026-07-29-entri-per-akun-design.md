# Desain: Entri Per Akun — SO Kartini

Tanggal: 2026-07-29
Status: disetujui Sopian (sesi 2026-07-29, lanjutan [hapus entri](2026-07-29-hapus-entri-rak-design.md))

## Masalah

Kartu "Hasil rak ini" menampilkan entri semua karyawan di rak itu, dan siapa pun boleh mengubahnya. Sopian ingin tiap karyawan hanya melihat dan mengelola hitungannya sendiri, supaya tidak saling menimpa — dan supaya terlihat siapa menghitung berapa (mis. Taxi sisa 200: Rian 150, Ichan 50).

## Tabrakan yang harus diselesaikan lebih dulu

Indeks unik `count_entries_open_unique` sekarang membatasi **satu entri terbuka per (rak, produk)** — bukan per orang. Kalau daftar disaring per akun tanpa mengubah indeks ini, karyawan kedua tidak melihat entri rekannya, mengira produk belum dihitung, mengisi form, lalu penyimpanannya ditolak `23505` dengan pesan "Sudah ada entri produk ini — buka dari daftar" — padahal entri itu tidak ada di daftarnya. Buntu.

## Keputusan produk

- **Angka dijumlahkan, bukan saling menimpa.** Indeks unik dilonggarkan jadi per orang, sehingga dua karyawan boleh punya entri sendiri untuk produk yang sama di rak yang sama. Laporan tidak perlu diubah: Rekap (`SUMIFS`), Template Olsera (`sum(Col7) group by` produk/satuan/sku/rak), dan Arsip Harian (`sum(Col5) group by` tanggal/sku) sudah menjumlahkan, dan tab Log tetap menyimpan rinciannya per orang lewat kolom Staff.
- **Ubah dan hapus dikunci ke milik sendiri**, dijaga RLS — bukan sekadar disembunyikan dari layar.
- **Baca tetap terbuka** (`using (true)`) supaya dashboard admin tetap melihat semua entri semua orang.
- **Upload juga per akun.** Tiap orang mengirim hitungannya sendiri. Konsekuensi yang diterima: kalau seseorang pulang tanpa Upload, entrinya menggantung dan hanya dia yang bisa mengirimnya (datanya tidak hilang — besok tinggal buka rak itu lalu Upload). Penangkalnya kartu "Progress rak" di dashboard admin yang menampilkan jumlah entri "terbuka", jadi Sopian tahu masih ada yang belum terkirim sebelum menarik laporan.

## Rancangan

### Database

```sql
drop index if exists count_entries_open_unique;
create unique index count_entries_open_unique
  on count_entries (rack, product_name, user_id) where uploaded_at is null;

drop policy if exists "update open entries" on count_entries;
create policy "update open entries" on count_entries
  for update to authenticated
  using (uploaded_at is null and auth.uid() = user_id)
  with check (uploaded_at is null and auth.uid() = user_id);

drop policy if exists "delete open entries" on count_entries;
create policy "delete open entries" on count_entries
  for delete to authenticated
  using (uploaded_at is null and auth.uid() = user_id);
```

Policy `read entries` dan `insert own entries` tidak diubah.

### Aplikasi

- `useEntries`: query `refresh` ditambah `.eq('user_id', session.user.id)`. Semua turunannya ikut menyesuaikan sendiri — `openEntries`, badge jumlah item, pencarian entri saat membuka produk, dan daftar "Hasil rak ini".
- `upload-rak`: klaim entri ditambah `.eq('user_id', user.id)`. Function sudah memanggil `getUser()` untuk autentikasi, jadi identitasnya sudah tersedia.

Tidak ada perubahan di halaman admin.

## Testing

Diverifikasi lewat smoke test terhadap Supabase live memakai **dua akun sementara** (bukan akun karyawan), autentikasi kunci anon supaya RLS benar-benar teruji:

1. A dan B masing-masing menyisipkan entri untuk produk yang sama di rak yang sama → keduanya berhasil (indeks baru).
2. A mencoba mengubah entri B → 0 baris. A mencoba menghapus entri B → 0 baris.
3. Query daftar milik A hanya mengembalikan entri A.
4. Upload sebagai A → hanya entri A yang terklaim; entri B tetap terbuka.
5. Bersihkan: baris uji di tab Log, entri uji, dan kedua akun sementara. Tab Log kembali ke jumlah baris semula.

Entri karyawan yang sedang berjalan tidak boleh tersentuh sama sekali.

## Di luar cakupan

- Admin mengirimkan entri karyawan yang lupa Upload.
- Rincian "siapa punya berapa entri terbuka" di dashboard admin (sekarang hanya total per rak).
- Membatasi izin baca.
