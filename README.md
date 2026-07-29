# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Functions:
  - `upload-rak` → Google Sheet "SO Toko Kartini":
    - **Log** = sumber data satu-satunya; jangan dihapus baris datanya (tidak ada backup).
    - **Rekap** & **Template Olsera** = satu hari sesuai kotak tanggal di `Rekap!G1` (kosong = tanggal SO terakhir yang ada di Log — bukan hari ini, karena `Log!A` menyimpan waktu input, dan upload lewat tengah malam bikin "hari ini" sudah ganti sementara SO terakhir masih kemarin).
    - **Arsip Harian** = semua hari (urut tanggal terbaru di atas).
  - `admin-create-user` → bikin akun staff dari halaman admin.
- Sync produk dari Master Pricelist:
  - Tombol **Sync produk** di halaman admin; jalan juga otomatis tiap malam pukul 03:00 WIB.
  - Halaman admin menampilkan waktu sync terakhir beserta ringkasannya, termasuk kalau job malam gagal — cek di situ kalau barang baru belum muncul.
  - `python scripts/sync_products.py` tetap ada sebagai cadangan kalau Edge Function bermasalah.
  - Pengaman: kalau pembacaan sheet menghasilkan kurang dari separuh jumlah produk aktif, sync dibatalkan dan dicatat gagal — supaya sheet yang bermasalah tidak menonaktifkan seluruh katalog.
- Setup spreadsheet: `cd scripts; python setup_sheet.py` (aman diulang di luar jam SO; tidak menulis ke baris data Log kalau sudah ada isi, tapi TETAP menulis ulang header `Log!A1:H1` dan MENGOSONGKAN `Rekap!G1` tiap kali dijalankan — jangan jalankan di tengah sesi SO).
- Akun staff: login sebagai `admin` → buka halaman Admin (dashboard + form buat akun), isi username & password.
  - Hapus/nonaktifkan akun: tanpa riwayat SO → hapus permanen; ada riwayat SO → nonaktif (SO tetap tersimpan, bisa diaktifkan via **Aktifkan** di baris yang sama); akun `admin` tidak bisa dihapus atau dinonaktifkan.
  - Cadangan: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
  - Cadangan CLI (break-glass): `cd scripts; python create_user.py <username> <password>`.
- Rak: tabel `racks` di Table Editor.
- Hasil rak ini (kartu hasil rak): karyawan bisa menghapus entri yang **belum di-upload** (mis. produk ternyata sudah dihitung di rak lain) — datanya dibuang jadi tidak ikut ter-upload. Entri yang **sudah** di-upload terkunci, tidak bisa dihapus dari app; perbaikannya dilakukan langsung di baris tab Log.
- Entri per akun: tiap karyawan hanya melihat, mengubah, menghapus, dan meng-upload hitungannya sendiri (dijaga aturan database RLS, bukan cuma tampilan); admin dashboard tetap menampilkan semua entri dari semua karyawan.
- Dua karyawan boleh menghitung produk yang sama di rak yang sama — angkanya dijumlahkan di Rekap, Template Olsera, dan Arsip Harian (dikelompokkan per SKU), sementara rincian per orang tetap terlihat di kolom Staff tab Log (contoh: Taxi total 200 — Rian 150, Ichan 50). Kalau keduanya isi tanggal ED yang beda untuk produk yang sama, Template Olsera cuma menyimpan ED terbaru (`max`) — jadi ED untuk produk yang dihitung terpisah begini tidak bisa diandalkan, cek langsung ke tab Log kalau perlu ED yang akurat.
- Saat karyawan mau menghitung produk yang sudah punya entri terbuka milik rekan di rak yang sama, halaman Hitung menampilkan peringatan read-only "sudah dihitung `<username>`: `<qty>`" di hasil pencarian maupun di form — supaya perhitungan ganda yang tidak disengaja kelihatan dari awal, sementara split kerja yang memang disengaja tetap bisa disimpan sebagai entri terpisah.
- Peringatan operasional: karena Upload per akun, karyawan yang belum menekan Upload akan menyisakan entri terbuka yang **hanya dia** yang bisa mengirim — datanya tidak hilang (bisa dibuka rak yang sama hari berikutnya dan di-upload), namun akan tidak muncul di laporan sampai itu dilakukan. Cek kartu "Progress rak" di dashboard admin (angka "N entri terbuka") dan kartu "Aktivitas karyawan" (keterangan "N belum di-upload" di baris orangnya) sebelum menarik laporan.
- Akun dinonaktifkan tapi masih ada entri terbuka: sekarang **ditolak** — pesan errornya minta karyawan itu Upload dulu. Alasannya: upload sekarang per akun, jadi entri terbuka milik akun yang dinonaktifkan tidak bisa dikirim siapa pun, termasuk admin. Kalau ini terjadi (mis. akun keburu dinonaktifkan sebelum Upload): **Aktifkan** akunnya lagi dari dashboard admin, minta karyawan itu login lalu tekan **Upload** di rak yang bersangkutan, baru nonaktifkan ulang.
- Verifikasi ulang aturan per-akun (RLS): `scripts/smoke_perakun.mjs` — bikin dua akun sementara, bukti pemisahan milik-sendiri (positif & negatif) dan upload per akun, lalu bersih-bersih sendiri. Perlu `SO_SERVICE_KEY` di environment; lihat komentar header file untuk cara jalanin dan peringatannya (nulis satu baris ke tab Log live yang harus dihapus manual sesudahnya). Jalankan sebelum mengubah schema.sql / policy `count_entries`, di luar jam SO aktif.
- Ganti password akun mana pun (admin maupun karyawan): klik dua kali **`GANTI PASSWORD.bat`** di root proyek. Password diketik di jendela itu dan tidak pernah ditulis ke berkas apa pun. Supabase Dashboard tidak bisa dipakai untuk ini karena email `@tokokartini.app` fiktif — tombol "reset password" di sana cuma mengirim email yang tidak akan pernah sampai.
- **Repo ini PUBLIK.** Jangan pernah menaruh kunci atau password asli di berkas mana pun di dalam folder proyek — riwayat Git menyimpannya selamanya walau berkasnya kemudian dihapus. Nilai rahasia tempatnya di `scripts/config.local.json` dan `.env.local`, keduanya sudah dikunci di luar repo. Di dokumen, tulis penanda seperti `<service_role_key>`, bukan nilainya.
  - Penjaga otomatis: `.githooks/pre-commit` menolak commit yang memuat kunci Supabase, token manajemen, kunci privat, JWT, atau password tertulis langsung. Aktif di clone ini; **kalau repo di-clone ulang di komputer lain, aktifkan lagi dengan `git config core.hooksPath .githooks`.**
  - Kalau ada baris aman yang kena tahan, tambahkan komentar `nosecret` di baris itu. Kalau mendesak: `git commit --no-verify`.
- Spec & plan: `docs/superpowers/`.
