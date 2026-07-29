-- Catatan tiap percobaan sync produk dari Master Pricelist.
-- Dibaca halaman admin untuk menampilkan "terakhir sync", dan dipakai melacak
-- kegagalan job malam yang tidak ada yang menunggui.
-- Hanya Edge Function (service role) yang menulis — tidak ada policy tulis.
-- Jalankan di Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
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
