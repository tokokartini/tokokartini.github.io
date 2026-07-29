# Desain: Sync Produk dari Web — SO Kartini

Tanggal: 2026-07-29
Status: disetujui Sopian (sesi 2026-07-29)

## Masalah

Kalau ada barang baru di Master Pricelist, produk itu belum muncul di app sampai Sopian membuka laptop dan menjalankan `python scripts/sync_products.py`. Butuh laptop, butuh ingat, dan tidak ada jejak kapan terakhir dijalankan.

## Keputusan produk

- **Tombol "Sync produk" di halaman admin** untuk sync langsung setelah menambah barang, **plus jalan otomatis tiap malam** sebagai jaring pengaman kalau lupa menekan.
- Hasilnya ditampilkan ringkas: `2753 produk — 12 baru, 3 dinonaktifkan`, dan keterangan `terakhir sync: <waktu WIB>` yang selalu terlihat di halaman admin.
- Script laptop `scripts/sync_products.py` **tetap ada** sebagai cadangan; logikanya tidak diubah.

## Modal yang sudah tersedia

Tidak butuh kredensial baru. Service account `point-coffee@claude-code-powershel.iam.gserviceaccount.com` sudah punya akses ke sheet Master Pricelist, dan kuncinya sudah terpasang di Supabase sebagai secret `GOOGLE_SA_EMAIL` / `GOOGLE_SA_KEY` (dipakai `upload-rak`). Pola tanda-tangan JWT Google-nya juga sudah ada di `supabase/functions/upload-rak/index.ts:8-38` dan tinggal dipakai ulang.

Yang baru hanya secret `MASTER_SHEET_ID` (id sheet Master Pricelist) — dibedakan dari `SHEET_ID` yang sudah dipakai untuk sheet SO.

## Rancangan

### Edge Function `sync-produk`

Port dari `scripts/sync_products.py`, logika parsing harus sama persis (kolom, perhitungan `mult`, aturan lewati/duplikat).

**Dua jalur autentikasi**, karena penjadwal tidak bisa login sebagai admin:

| Pemanggil | Cara | `source` yang dicatat |
|---|---|---|
| Tombol di halaman admin | JWT user, email harus `admin@tokokartini.app` | `manual` |
| Penjadwal malam (pg_cron) | `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>` | `jadwal` |

Selain keduanya → 401/403.

**Pengaman sync massal.** Job otomatis tidak ada yang menunggui, jadi kalau pembacaan sheet gagal separuh jalan dan mengembalikan sedikit baris, langkah "nonaktifkan SKU yang hilang dari sheet" bisa menonaktifkan hampir seluruh katalog tanpa ada yang sadar. Karena itu: bila jumlah produk hasil parsing **kurang dari separuh** jumlah produk aktif yang ada sekarang, sync dibatalkan — tidak ada upsert, tidak ada penonaktifan — dan kegagalannya dicatat. Script laptop tidak punya pengaman ini; di sini perlu karena tak ada manusia yang mengawasi.

### Tabel `sync_runs`

Satu baris per percobaan sync, dipakai untuk menampilkan "terakhir sync" dan untuk melacak kegagalan job malam:

```sql
create table sync_runs (
  id bigint generated always as identity primary key,
  ran_at timestamptz not null default now(),
  source text not null,              -- 'manual' | 'jadwal'
  ok boolean not null,
  total int not null default 0,      -- produk hasil parsing
  added int not null default 0,      -- SKU yang belum ada di database
  deactivated int not null default 0,
  skipped int not null default 0,    -- baris dilewati karena satuan kosong
  error text
);
```

RLS: `select` untuk `authenticated` (halaman admin membacanya). Tidak ada policy insert/update/delete — hanya function yang menulis, memakai service role.

### Penjadwal

`pg_cron` + `pg_net` (keduanya tersedia di project ini, belum terpasang). Jadwal `0 20 * * *` UTC = **03:00 WIB**, jam sepi supaya tidak berbenturan dengan SO malam. Job memanggil Edge Function dengan service role key.

### Halaman admin

Kartu baru **Produk**: tombol "Sync produk", keterangan `terakhir sync: <waktu> · <ringkasan>`, dan pesan hasil setelah ditekan. Baris terakhir `sync_runs` dibaca saat halaman dimuat.

## Testing

- Unit test fungsi parsing hasil port, dengan fixture baris sheet yang mencakup: satuan kosong (dilewati), SKU duplikat, `isi` rusak/`-` (mult jadi 1), dan baris pemisah `===`. Hasilnya dibandingkan dengan keluaran `parse_rows` Python untuk fixture yang sama.
- Smoke test live: panggil function sebagai admin, bandingkan jumlah produk aktif sebelum/sesudah (harus tetap 2753 karena master belum berubah), pastikan `sync_runs` bertambah satu baris `ok=true`, dan pastikan pengaman massal menolak pemanggilan non-admin.
- Penjadwal diuji dengan menjalankan perintah `cron.schedule`-nya sekali secara manual, lalu memeriksa baris `sync_runs` bersumber `jadwal`.

## Di luar cakupan

- Mengubah logika parsing atau struktur Master Pricelist.
- Menghapus `scripts/sync_products.py`.
- Notifikasi kalau job malam gagal (untuk sekarang cukup terlihat di halaman admin).
