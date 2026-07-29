-- Izinkan karyawan membuang entri yang salah masuk (mis. produk ternyata sudah
-- dihitung di rak lain). Dibatasi ke entri yang BELUM di-upload: entri terupload
-- sudah punya baris pasangan di tab Log spreadsheet, dan menghapusnya di sini
-- akan meninggalkan baris yatim yang tidak bisa dilacak.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
create policy "delete open entries" on count_entries
  for delete to authenticated using (uploaded_at is null);
