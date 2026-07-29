# Desain: Halaman Admin (Dashboard + Kelola Akun) — SO Kartini

Tanggal: 2026-07-29
Status: disetujui Sopian (brainstorming sesi 2026-07-29)

## Tujuan

Akun `admin` saat login tidak masuk alur stok opname, melainkan halaman admin berisi:

1. Dashboard pemantauan SO (progress rak, aktivitas karyawan, entri terbaru).
2. Kelola akun: membuat akun karyawan langsung dari web.

Alur karyawan (Home → Count) tidak berubah.

## Keputusan produk

- Admin = **username `admin` saja**, hardcode. Tidak ada sistem role di database.
- Kelola akun = **bikin akun saja**. Tanpa reset password / hapus (reset & hapus tetap via Supabase Dashboard atau `scripts/create_user.py`).
- Dashboard tanpa tombol upload rak — upload tetap dari halaman hitung.
- Refresh dashboard manual (tombol "Muat ulang"), tanpa auto-refresh.

## Arsitektur

- `App.jsx`: jika `username === 'admin'` → render `Admin.jsx`; selain itu alur lama.
- Blokir admin dari SO hanya di tampilan (cukup — admin adalah pemilik).
- Dashboard membaca `count_entries` + `racks` langsung dari browser memakai RLS read yang sudah ada.
- Pembuatan akun lewat Edge Function baru **`admin-create-user`** (pola sama dengan `upload-rak`): verifikasi JWT pengirim → tolak jika email ≠ `admin@tokokartini.app` → aksi memakai `SUPABASE_SERVICE_ROLE_KEY`. Kunci rahasia tidak pernah sampai ke browser.

## Komponen

### `src/pages/Admin.jsx` (baru)

Tiga kartu dashboard + satu kartu kelola akun:

1. **Progress rak** — per rak: jumlah entri terbuka, jumlah terupload, waktu entri terakhir. Rak tanpa entri ditandai "belum dihitung".
2. **Aktivitas karyawan** — per username: entri hari ini (WIB), total entri, waktu terakhir input.
3. **Entri terbaru** — 20 entri terakhir: jam, karyawan, rak, produk, qty. Tombol "Muat ulang".
4. **Kelola akun** — form username + password (min 8 karakter) + tombol Buat; di bawahnya daftar akun yang ada. Username dipaksa huruf kecil (konsisten dengan `Login.jsx`).

Data dashboard: satu query `count_entries` (kolom `username, rack, product_name, qty_total, created_at, uploaded_at`) + query `racks`, lalu direkap di browser (helper murni di `src/lib/`, bisa di-unit-test).

### Edge Function `supabase/functions/admin-create-user/index.ts` (baru)

- Request: `{action: "create", username, password}` atau `{action: "list"}`.
- Cek auth: `getUser()` dari JWT; jika email ≠ `admin@tokokartini.app` → 403.
- `create`: email = `<username huruf kecil>@tokokartini.app`, `email_confirm: true` via admin API. Username duplikat → error jelas.
- `list`: daftar user (email, created_at) via admin API — dibutuhkan karena daftar user tidak bisa dibaca dari browser.
- Secrets: memakai `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` bawaan (tidak perlu secret baru).

## Error handling

- Username sudah dipakai → pesan "username sudah dipakai".
- Password < 8 karakter → ditolak di form sebelum kirim.
- Function gagal → pesan gagal, tidak ada akun setengah jadi.
- Dashboard gagal memuat → pesan "gagal memuat, coba lagi" + tombol ulang.
- Pemanggil bukan admin → 403 di server (cek frontend hanya kosmetik).

## Testing

- Unit test helper rekap dashboard (per rak, per karyawan, entri terbaru) — pola `groupProducts.test.js`.
- Manual: login `admin` → dashboard tampil, tidak ada alur hitung; login `tes` → SO normal; buat akun baru dari web → login akun itu → bisa SO.

## Deploy

- Frontend: push `main` → GitHub Pages otomatis.
- Edge Function: `npx supabase functions deploy admin-create-user --project-ref qfqulgkpbjceizrapyom --use-api` — butuh `SUPABASE_ACCESS_TOKEN` baru dari Sopian saat deploy.

## Di luar cakupan

- Reset/hapus akun dari web.
- Sistem role multi-admin.
- Auto-refresh / realtime dashboard.
- Blokir SO untuk admin di level database.
