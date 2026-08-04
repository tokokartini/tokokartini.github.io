-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom)
create table if not exists products (
  id bigint generated always as identity primary key,
  sku text unique not null,
  product_name text not null,
  variant text not null,
  mult numeric not null default 1,      -- 1 satuan ini = mult satuan dasar
  unit_order int not null default 0,    -- 0 = satuan terbesar (grosir)
  category text not null default '',
  brand text not null default '',
  active boolean not null default true
);

create table if not exists racks (
  id bigint generated always as identity primary key,
  name text unique not null,
  sort int not null default 0,
  active boolean not null default true
);

create table if not exists count_entries (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  user_id uuid not null references auth.users (id),
  username text not null,
  rack text not null,
  product_name text not null,
  units jsonb not null,
  qty_total numeric not null check (qty_total >= 0),
  expired_date date,
  uploaded_at timestamptz
);

-- satu entri terbuka per produk per rak per orang
create unique index if not exists count_entries_open_unique
  on count_entries (rack, product_name, user_id) where uploaded_at is null;
create index if not exists count_entries_rack_idx on count_entries (rack, uploaded_at);

alter table products enable row level security;
alter table racks enable row level security;
alter table count_entries enable row level security;

create policy "read products" on products for select to authenticated using (true);
create policy "read racks" on racks for select to authenticated using (active);
create policy "read entries" on count_entries for select to authenticated using (true);
create policy "insert own entries" on count_entries
  for insert to authenticated with check (auth.uid() = user_id and uploaded_at is null);
create policy "update open entries" on count_entries
  for update to authenticated
  using (uploaded_at is null and auth.uid() = user_id)
  with check (uploaded_at is null and auth.uid() = user_id);
create policy "delete open entries" on count_entries
  for delete to authenticated using (uploaded_at is null and auth.uid() = user_id);

insert into racks (name, sort) values
  ('Gudang Packaging', 1), ('Gudang Bahan Kue', 2), ('Gudang Ciherang', 3),
  ('Area Display', 4), ('Gudang Dapur Cherry', 5)
on conflict (name) do nothing;

create table if not exists sync_runs (
  id bigint generated always as identity primary key,
  ran_at timestamptz not null default now(),
  source text not null,
  ok boolean not null,
  total int not null default 0,
  added int not null default 0,
  deactivated int not null default 0,
  skipped int not null default 0,
  error text
);

create index if not exists sync_runs_ran_at_idx on sync_runs (ran_at desc);

alter table sync_runs enable row level security;

create policy "read sync runs" on sync_runs for select to authenticated using (true);
