-- Entri jadi milik pribadi tiap karyawan.
--
-- 1) Indeks unik dilonggarkan jadi per orang. Sebelumnya satu entri terbuka per
--    (rak, produk) untuk semua orang — begitu daftar disaring per akun, karyawan
--    kedua tidak melihat entri rekannya, mengisi form, lalu ditolak 23505 tanpa
--    bisa menemukan entri yang menghalanginya. Dengan indeks per orang, keduanya
--    punya entri sendiri dan laporan menjumlahkannya (Rekap/Template/Arsip semua
--    sudah group by SKU + sum qty).
-- 2) Ubah dan hapus dikunci ke milik sendiri.
-- Policy "read entries" sengaja dibiarkan terbuka: dashboard admin membacanya.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).

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
