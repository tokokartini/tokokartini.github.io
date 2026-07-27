# Desain: Stok Opname Kartini

Tanggal: 2026-07-27
Status: menunggu review user

## Ringkasan

Web app stok opname untuk Toko Kartini, berbasis salinan `so-labelshop` yang dirombak.
Staff menghitung stok per rak di HP; hasil masuk Supabase, lalu di-Upload per rak ke
Google Sheet yang otomatis menghasilkan rekap dan template import Olsera.

Referensi tampilan: app "Stok Opname Kartini" (screenshot di
`C:\Users\COMPUTER\Documents\New folder`) — login username+password, pilih rak,
input qty per satuan dengan konversi, daftar "Hasil rak ini", tombol Upload.

## Keputusan yang sudah disepakati

| Topik | Keputusan |
|---|---|
| Basis kode | Salin repo `so-labelshop`, rombak (pendekatan A) |
| Produk | Sama dengan LabelShop, sync dari Master Pricelist |
| Database | Supabase project **baru** (akun email baru, sudah dibuat) |
| Hosting | GitHub Pages, akun baru `tokokartini`, repo `tokokartini.github.io` → URL `https://tokokartini.github.io` (fallback nama: `tokokartini-id`, `sotokokartini`) |
| Output | Google Sheet baru "SO Toko Kartini": tab Log + Rekap + Template Olsera |
| Upload ke Sheet | Tombol Upload per rak, via Supabase Edge Function |
| Konversi satuan | Data dari Master Pricelist (kolom konversi; verifikasi format sebelum implementasi) |
| Rak | Tabel `racks` di Supabase, dikelola admin via Dashboard |
| Fitur dibuang | Antrean offline, halaman riwayat + badge total, tombol export CSV di app |
| Fitur ditambah | Input multi-satuan dengan konversi; edit entri sebelum upload; output ke Sheet |
| Akun staff | Dibuat admin (Sopian) via Supabase Dashboard |
| Warna | Hijau tua (utama) + orange (aksen), latar krem terang |

## Arsitektur

Empat komponen:

1. **Frontend** — Vite static app (rombakan so-labelshop), deploy otomatis ke GitHub
   Pages tiap push `main` via Actions.
2. **Supabase project baru** — Auth + PostgreSQL + Edge Function.
3. **Google Sheet "SO Toko Kartini"** — tiga tab; hanya tab Log yang ditulis mesin,
   dua tab lain formula.
4. **Script sync** — `scripts/sync_products.py` (versi Kartini): Master Pricelist →
   tabel `products`, termasuk data konversi satuan. Dijalankan Sopian dari laptop
   tiap master berubah.

Kunci service account Google disimpan sebagai **secret di Supabase Edge Function** —
tidak pernah ada di repo publik. Frontend hanya bisa memanggil function dengan JWT
user yang login.

## Model data (Supabase)

- `products` — read-only untuk staff. Kolom: sku, nama, variant, satuan dasar,
  daftar satuan konversi (mis. `[{label:"Krtn (15 Kg)", multiplier:60}, ...]`,
  bentuk kolom final ditentukan saat implementasi setelah cek format master).
- `count_entries` — entri hitungan. Kolom inti: id, client_id (idempotensi),
  user_id, rack, sku, qty_total, rincian_satuan (JSON), expired_date (nullable),
  created_at, updated_at, `uploaded_at` (nullable — penanda sudah masuk Sheet).
  RLS: staff boleh insert; boleh **update milik sendiri selama `uploaded_at` masih
  kosong**; tidak boleh delete.
- `racks` — daftar rak (nama, urutan, aktif). Read-only untuk staff; admin kelola
  via Dashboard.

## Alur data

1. Login → beranda "Halo, {nama}! Semangat ya 🔥" → pilih rak → Mulai Hitung.
2. Cari produk → form input per satuan (mis. Krtn ×60, Kg ×4, pcs ×1) → total pcs
   dihitung otomatis → ED opsional → Simpan → insert langsung ke Supabase.
3. Tidak ada antrean offline. Simpan gagal → pesan error + "Coba lagi", angka tetap
   di form.
4. Entri tampil di "Hasil rak ini". **Satu produk = satu entri per rak**: klik entri
   (atau cari produk yang sama lagi) → form terbuka dengan angka lama → ubah/tambah →
   Simpan meng-update entri yang sama, bukan bikin baris baru.
5. Upload → Edge Function kirim semua entri rak yang `uploaded_at`-nya kosong ke tab
   Log, lalu set `uploaded_at`. Boleh ditekan berulang; tidak ada baris dobel.
   Setelah upload, entri terkunci (tidak bisa diedit dari app; koreksi oleh admin
   di Sheet/Supabase).
6. Tab Rekap dan Template Olsera terisi otomatis via formula begitu Log bertambah.

## Google Sheet

- **Log** (ditulis Edge Function): waktu (WIB), staff, rak, produk, variant, SKU,
  qty total, rincian satuan (teks, mis. "1 Krtn + 2 Kg"), expired_date.
- **Rekap** (formula): total qty per SKU dari seluruh Log — pembanding stok sistem.
- **Template Olsera** (formula): `time, product, variant, sku, qty, rack,
  expired_date` mengikuti format import SO Olsera (sama seperti export app lama;
  duplikat sku+rak sudah tidak terjadi karena satu produk satu entri per rak).

## Tampilan

- Warna: hijau tua utama, aksen orange, latar krem terang. Judul "📦 Stok Opname
  Kartini".
- **Login**: Username + Password (di belakang layar dipetakan ke email internal
  `username@tokokartini.app` untuk Supabase Auth). Teks "Belum punya akun? Minta
  dibuatkan admin."
- **Beranda**: "Halo, {nama}! Semangat ya 🔥", tombol Keluar, dropdown "Rak yang
  dihitung" (dari tabel `racks`), tombol "Mulai Hitung".
- **Halaman hitung**: header nama · rak, badge jumlah item, tombol "Ganti Rak",
  status sinkron, kotak cari produk, form multi-satuan + ED + angka total besar +
  Simpan/Batal, daftar "Hasil rak ini" (klik = edit), tombol Upload.

## Penanganan error

- Simpan gagal: error jelas + coba lagi, form tidak direset.
- Upload gagal sebagian: yang sudah masuk tertanda `uploaded_at`; Upload ulang hanya
  mengirim sisanya.
- Sesi kadaluarsa: redirect ke login; data tersimpan aman.
- Produk tidak ketemu: pesan "tidak ada — cek master / minta sync".

## Pengujian

- Tes otomatis: logika konversi satuan (input per satuan → qty total), penyusunan
  baris Log, filter entri belum-terupload.
- Tes manual di HP: login, hitung, edit entri, ganti rak, upload, verifikasi isi
  Sheet (Log/Rekap/Template) — sebelum dipakai staff.

## Langkah setup (dipandu satu-satu)

1. ✅ Email baru + Supabase project baru (sudah dibuat user).
2. Akun GitHub baru `tokokartini` (user, sedang berjalan).
3. Google Sheet baru + akses service account (Claude).
4. Salin & rombak kode, setup Supabase (schema, RLS, Edge Function, secrets),
   deploy Pages, sync produk, buat akun staff, tes HP.

## Di luar cakupan

- Mode offline / antrean.
- Halaman riwayat & badge total.
- Export CSV dari app.
- Multi-toko dalam satu app (LabelShop tetap app terpisah).
