-- Penjualan harian dari export POS, diupload lewat halaman admin aplikasi.
--
-- Menutup lubang terakhir hitungan stok: penjualan mengurangi Area Display, dan
-- selama ini angkanya cuma bisa masuk lewat skrip di laptop Sopian.
--
-- Kenapa baris mentah per item, bukan sudah dijumlah per SKU:
-- satu tanggal melayani DUA pertanyaan yang bentuknya beda. Stok cuma butuh
-- "berapa keluar hari itu per SKU" (boleh dijumlah). Piutang butuh "siapa nunggak
-- berapa" (harus per nota + pelanggan). Kalau disimpan sudah terjumlah, piutang
-- tidak bisa dihitung lagi tanpa upload ulang. Sebaliknya, dari baris mentah dua
-- duanya bisa. Ukurannya kecil: ~400 baris/hari, ~12.000 baris/bulan.
--
-- Kolom yang SENGAJA tidak disimpan, walau ada di file export: email karyawan
-- (2.528 baris), nomor HP + alamat pelanggan, HPP, profit, komisi, nomor rekening.
-- Semuanya tidak dipakai hitungan stok maupun piutang. Aplikasi memotongnya di
-- browser sebelum mengirim, jadi data itu tidak pernah meninggalkan HP Sopian.
--
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
-- WAJIB dijalankan SEBELUM aplikasi versi baru ter-deploy: kalau kebalik, tombol
-- upload gagal semua, bukan cuma yang baru.

create table if not exists penjualan_harian (
  id bigint generated always as identity primary key,
  -- Tanggal transaksi dari kolom `order date`, BUKAN tanggal upload. Ini kunci
  -- penggantian: upload ulang mengganti seluruh baris tanggal ini.
  tanggal date not null,
  -- Nomor nota. Dipakai mengelompokkan piutang per transaksi, dan menelusuri
  -- balik ke POS kalau ada angka yang mencurigakan.
  order_no text not null default '',
  -- Boleh KOSONG. Di export 17-23 Agu ada 39 baris tanpa SKU -- barang yang
  -- diketik manual di kasir karena belum ada di master ("kertas nasi roll",
  -- "duo 40 hitam", Rp 915.500). Itu barang yang terjual tapi stoknya tidak
  -- dilacak siapa pun, jadi WAJIB tetap tersimpan dan dilaporkan, bukan dibuang.
  sku text not null default '',
  produk text not null default '',
  -- Tidak dibatasi > 0: kalau nanti ada retur, bentuknya belum ketahuan (kolom
  -- `return date` ada di export tapi kosong sepanjang minggu contoh). Qty minus
  -- harus bisa masuk tanpa migrasi lagi.
  qty numeric not null,
  omzet numeric not null default 0,
  -- Dari kolom `paid`. TEMPO yang belum dibayar = false. Statusnya BERUBAH di
  -- baris tanggal aslinya waktu pelanggan melunasi (di contoh: 45 baris masih
  -- nunggak, 21 baris TEMPO sudah lunas) -- dan tidak ada kolom yang mencatat
  -- KAPAN dibayar. Jadi piutang cuma bisa disegarkan dengan meng-upload ulang
  -- rentang tanggal lama. Rencananya sekali di akhir bulan, waktu pelanggan tempo
  -- memang jatuh tempo.
  lunas boolean not null default true,
  -- CASH / QRIS BNI / TEMPO / BNI Transfer / EDC BNI. Disimpan supaya "tempo yang
  -- sudah lunas" bisa dibedakan dari "tunai biasa" -- keduanya lunas = true.
  cara_bayar text not null default '',
  -- Terisi di 45 dari 45 baris tempo, jadi piutang bisa dirinci per pelanggan
  -- (MajaKoffie, Coffee Bawa, Chery Bakes House), bukan cuma total.
  pelanggan text not null default '',
  diunggah_pada timestamptz not null default now(),
  diunggah_oleh uuid references auth.users (id)
);

-- Penggantian per tanggal dan pembacaan Python dua-duanya menyaring tanggal.
create index if not exists penjualan_tanggal_idx on penjualan_harian (tanggal);

-- Kolom Terjual tab Stok menjumlah per SKU dalam rentang tanggal.
create index if not exists penjualan_sku_idx on penjualan_harian (sku, tanggal);

-- Daftar piutang: yang belum lunas saja, dikelompokkan per pelanggan.
create index if not exists penjualan_piutang_idx
  on penjualan_harian (pelanggan, tanggal) where lunas = false;

-- SENGAJA TIDAK ADA indeks unik. Satu SKU boleh muncul berkali-kali dalam sehari
-- (nota berbeda), bahkan dua kali dalam satu nota. Yang menjamin upload ulang
-- tidak menggandakan baris adalah hapus-lalu-isi di dalam ganti_penjualan(),
-- bukan constraint. Indeks unik di sini justru akan MENOLAK data yang sah.

alter table penjualan_harian enable row level security;

-- Ini angka omzet, margin pelanggan, dan daftar hutang. Bukan hitungan rak yang
-- semua karyawan memang perlu lihat. Jadi dikunci ke akun admin saja -- melonggarkan
-- nanti gampang, menarik balik omzet yang sudah terlanjur terbaca tidak bisa.
--
-- Aplikasi menentukan admin lewat `username === 'admin'` di App.jsx, dan itu cuma
-- tampilan. Yang benar-benar menjaga adalah policy di bawah, dicek dari email di
-- dalam JWT -- tidak bisa dipalsukan dari browser.
--
-- Skrip Python memakai service_role key, yang melewati RLS, jadi jadwal malam
-- tetap bisa membaca tabel ini tanpa policy tambahan.
--
-- Tiap policy dibuang dulu supaya berkas ini aman dijalankan ulang: create policy
-- tidak punya varian IF NOT EXISTS.
drop policy if exists "admin baca penjualan" on penjualan_harian;
create policy "admin baca penjualan" on penjualan_harian
  for select to authenticated
  using ((auth.jwt() ->> 'email') = 'admin@tokokartini.app');

drop policy if exists "admin tulis penjualan" on penjualan_harian;
create policy "admin tulis penjualan" on penjualan_harian
  for insert to authenticated
  with check ((auth.jwt() ->> 'email') = 'admin@tokokartini.app');

drop policy if exists "admin hapus penjualan" on penjualan_harian;
create policy "admin hapus penjualan" on penjualan_harian
  for delete to authenticated
  using ((auth.jwt() ->> 'email') = 'admin@tokokartini.app');


-- Ganti seluruh baris untuk tanggal-tanggal yang ada di dalam kiriman.
--
-- GANTI, bukan tambah. Kalau cuma menambah, transaksi yang dibatalkan di POS akan
-- nyangkut di sini selamanya -- barisnya tidak pernah muncul lagi di export, jadi
-- tidak ada yang menghapusnya. Mengganti seluruh tanggal membuat sheet selalu sama
-- dengan POS untuk tanggal itu.
--
-- Satu fungsi = satu transaksi, jadi hapus dan isi tidak bisa terpisah. Tanpa ini,
-- gagal di tengah meninggalkan tanggal itu KOSONG dan penjualan sehari hilang diam
-- diam -- persis pola kecelakaan 2026-07-30 waktu tulis-balik Log memakan 7 entri.
--
-- `security invoker` (bawaan) disengaja: RLS di atas ikut berlaku, jadi fungsi ini
-- tidak jadi pintu belakang yang melewati kunci admin.
create or replace function ganti_penjualan(p_baris jsonb)
returns jsonb
language plpgsql
as $$
declare
  v_tanggal date[];
  v_min date;
  v_maks date;
  v_hapus bigint;
  v_isi bigint;
begin
  if p_baris is null or jsonb_typeof(p_baris) <> 'array' then
    raise exception 'p_baris harus berupa array JSON';
  end if;

  if jsonb_array_length(p_baris) = 0 then
    raise exception 'kiriman kosong -- tidak ada tanggal yang boleh dihapus';
  end if;

  -- Batas kewarasan. Bukan cerewet: kalau browser salah membaca kolom tanggal,
  -- tanpa cek ini fungsinya akan MENGHAPUS tanggal yang benar lalu mengisinya
  -- dengan sampah, dan tidak ada yang tahu sampai angka displaynya aneh.
  if jsonb_array_length(p_baris) > 200000 then
    raise exception 'kiriman % baris, terlalu besar -- periksa filenya',
      jsonb_array_length(p_baris);
  end if;

  select array_agg(distinct (b ->> 'tanggal')::date)
    into v_tanggal
    from jsonb_array_elements(p_baris) b;

  select min(t), max(t) into v_min, v_maks from unnest(v_tanggal) t;

  if v_min < date '2020-01-01' or v_maks > current_date + 1 then
    raise exception 'tanggal di luar akal: % sampai % -- periksa kolom order date',
      v_min, v_maks;
  end if;

  delete from penjualan_harian where tanggal = any(v_tanggal);
  get diagnostics v_hapus = row_count;

  insert into penjualan_harian
    (tanggal, order_no, sku, produk, qty, omzet, lunas, cara_bayar, pelanggan, diunggah_oleh)
  select (b ->> 'tanggal')::date,
         coalesce(b ->> 'order_no', ''),
         coalesce(b ->> 'sku', ''),
         coalesce(b ->> 'produk', ''),
         (b ->> 'qty')::numeric,
         coalesce((b ->> 'omzet')::numeric, 0),
         coalesce((b ->> 'lunas')::boolean, true),
         coalesce(b ->> 'cara_bayar', ''),
         coalesce(b ->> 'pelanggan', ''),
         auth.uid()
    from jsonb_array_elements(p_baris) b;
  get diagnostics v_isi = row_count;

  return jsonb_build_object(
    'tanggal_awal', v_min,
    'tanggal_akhir', v_maks,
    'jumlah_tanggal', array_length(v_tanggal, 1),
    'dihapus', v_hapus,
    'ditulis', v_isi
  );
end;
$$;

revoke all on function ganti_penjualan(jsonb) from public;
grant execute on function ganti_penjualan(jsonb) to authenticated;
