-- Mutasi barang antar lokasi: barang datang, isi ulang display, pindah antar gudang.
--
-- Tabel terpisah dari count_entries, BUKAN kolom tambahan di sana. Alasannya:
-- count_entries menjawab "berapa isi rak ini saat SO", movements menjawab "barang
-- pindah dari mana ke mana". Aturan uniknya beda (SO: satu entri per rak+produk,
-- mutasi: satu entri per pasangan lokasi+produk), qty 0 sah di SO tapi tidak di
-- mutasi, dan tab sheet tujuannya beda. Digabung berarti setiap query SO harus
-- ikut menyaring jenis, dan format Log 9 kolom yang sudah stabil ikut goyang.
--
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).

create table if not exists movements (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_id uuid not null references auth.users (id),
  username text not null,
  -- Jenis disimpan, bukan disimpulkan dari nama lokasi. Kalau disimpulkan, ganti
  -- nama lokasi (pernah terjadi: "Rak 1" -> "Gudang Packaging") diam-diam
  -- mengubah arti baris lama.
  jenis text not null check (jenis in ('Datang', 'Isi Ulang', 'Pindah')),
  from_loc text not null,
  to_loc text not null,
  nota text not null default '',
  product_name text not null,
  units jsonb not null,
  -- Beda dengan SO: qty 0 tidak masuk akal untuk perpindahan barang, jadi ditolak
  -- di sini supaya baris kosong tidak pernah sampai ke sheet.
  qty_total numeric not null check (qty_total > 0),
  uploaded_at timestamptz,
  constraint movements_lokasi_beda check (from_loc <> to_loc)
);

-- Satu entri terbuka per pasangan lokasi + produk + orang, supaya produk yang sama
-- diketik dua kali membuka entri lama (edit in place), bukan menumpuk baris dobel.
create unique index if not exists movements_open_unique
  on movements (from_loc, to_loc, product_name, user_id) where uploaded_at is null;

-- Daftar surat jalan yang sedang dibuka petugas.
create index if not exists movements_open_idx
  on movements (user_id, uploaded_at);

-- Dasar daftar "sering diisi ulang" di halaman isi ulang display.
create index if not exists movements_jenis_idx
  on movements (jenis, created_at desc);

alter table movements enable row level security;

-- Pola izin disamakan dengan count_entries: baca terbuka (dashboard admin nanti
-- membacanya), tulis/ubah/hapus terkunci ke milik sendiri dan hanya selama entri
-- belum terkirim ke sheet.
create policy "read movements" on movements
  for select to authenticated using (true);
create policy "insert own movements" on movements
  for insert to authenticated with check (auth.uid() = user_id and uploaded_at is null);
create policy "update open movements" on movements
  for update to authenticated
  using (uploaded_at is null and auth.uid() = user_id)
  with check (uploaded_at is null and auth.uid() = user_id);
create policy "delete open movements" on movements
  for delete to authenticated
  using (uploaded_at is null and auth.uid() = user_id);
