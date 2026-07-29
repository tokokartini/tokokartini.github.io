-- Jadwal malam untuk sync-produk (pg_cron + pg_net), sebagaimana benar-benar
-- diterapkan lewat Supabase Dashboard > SQL Editor (project qfqulgkpbjceizrapyom).
-- Ini catatan tertulisnya -- tanpa file ini, `pg_cron`/`pg_net`/secret Vault/job-nya
-- cuma ada di database live dan hilang total kalau rebuild dari schema.sql.
--
-- '0 20 * * *' adalah UTC -- itu 03:00 WIB (UTC+7).
-- JANGAN PERNAH commit isi kunci service role yang asli. Nilai Vault di bawah
-- adalah PLACEHOLDER -- ganti dengan kunci sungguhan langsung di SQL Editor saat
-- dijalankan, jangan pernah taruh kuncinya di file yang di-commit ke git.

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Jalankan sekali saat setup. Ganti 'ISI-DENGAN-SERVICE-ROLE-KEY-ASLI-SAAT-DIJALANKAN'
-- dengan kunci sungguhan dari Project Settings > API -- HANYA di SQL Editor,
-- TIDAK PERNAH ditulis ke file/commit ini.
select vault.create_secret(
  'ISI-DENGAN-SERVICE-ROLE-KEY-ASLI-SAAT-DIJALANKAN', -- jangan commit nilainya
  'sync_service_key',
  'Service role key untuk sync-produk dipanggil oleh pg_cron jam 03:00 WIB'
);

-- Job harian: panggil Edge Function sync-produk dengan Authorization dari Vault
-- (bukan kunci mentah di definisi job -- kunci tidak pernah tampil di sini).
select cron.schedule(
  'sync-produk-harian',
  '0 20 * * *', -- UTC; 03:00 WIB
  $$
  select net.http_post(
    url := 'https://qfqulgkpbjceizrapyom.supabase.co/functions/v1/sync-produk',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (
        select decrypted_secret from vault.decrypted_secrets where name = 'sync_service_key'
      )
    ),
    body := '{}'::jsonb
  );
  $$
);
