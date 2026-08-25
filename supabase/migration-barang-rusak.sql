-- Barang rusak / kadaluarsa / dipakai toko: barang keluar dari stok BUKAN karena
-- terjual dan bukan karena pindah lokasi.
--
-- Sengaja memakai tabel `movements` yang sudah ada, bukan tabel baru. Bentuknya
-- memang mutasi: barang keluar dari satu lokasi. Bedanya cuma tujuannya lokasi
-- maya `Barang Rusak`, persis seperti `Barang Datang` yang sudah jadi lokasi maya
-- untuk asal. Dengan begitu rumus saldo di scripts/hitung_saldo.py sudah otomatis
-- mengurangi stok asalnya tanpa diubah sama sekali.
--
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).

-- 1. Izinkan jenis baru. Constraint lama dibuang dulu karena CHECK tidak bisa
--    diubah di tempat; namanya bawaan Postgres untuk `check` yang menempel di kolom.
alter table movements drop constraint if exists movements_jenis_check;
alter table movements add constraint movements_jenis_check
  check (jenis in ('Datang', 'Isi Ulang', 'Pindah', 'Rusak'));

-- 2. Kolom sebab. Kosong untuk tiga jenis lama, jadi default '' bukan null --
--    menyamai kolom `nota` supaya tidak ada dua cara menulis "tidak diisi".
alter table movements add column if not exists sebab text not null default '';

-- 3. Sebab WAJIB diisi untuk jenis Rusak, dan wajib KOSONG untuk jenis lain.
--    Tanpa aturan kedua, sebab bisa nyangkut di baris pindah gudang dan tab
--    laporan Barang Rusak ikut menghitungnya.
alter table movements drop constraint if exists movements_sebab_rusak;
alter table movements add constraint movements_sebab_rusak
  check ((jenis = 'Rusak' and sebab <> '') or (jenis <> 'Rusak' and sebab = ''));

-- 4. Dasar tab laporan Barang Rusak dan baris kerugian di tab Ringkasan.
create index if not exists movements_rusak_idx
  on movements (jenis, created_at desc) where jenis = 'Rusak';
