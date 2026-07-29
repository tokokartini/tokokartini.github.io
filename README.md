# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Functions:
  - `upload-rak` → Google Sheet "SO Toko Kartini":
    - **Log** = sumber data satu-satunya; jangan dihapus baris datanya (tidak ada backup).
    - **Rekap** & **Template Olsera** = satu hari sesuai kotak tanggal di `Rekap!G1` (kosong = tanggal SO terakhir yang ada di Log — bukan hari ini, karena `Log!A` menyimpan waktu input, dan upload lewat tengah malam bikin "hari ini" sudah ganti sementara SO terakhir masih kemarin).
    - **Arsip Harian** = semua hari (urut tanggal terbaru di atas).
  - `admin-create-user` → bikin akun staff dari halaman admin.
- Sync produk dari Master Pricelist: `cd scripts; python sync_products.py`.
- Setup spreadsheet: `cd scripts; python setup_sheet.py` (aman diulang di luar jam SO; tidak menulis ke baris data Log kalau sudah ada isi, tapi TETAP menulis ulang header `Log!A1:H1` dan MENGOSONGKAN `Rekap!G1` tiap kali dijalankan — jangan jalankan di tengah sesi SO).
- Akun staff: login sebagai `admin` → buka halaman Admin (dashboard + form buat akun), isi username & password.
  - Hapus/nonaktifkan akun: tanpa riwayat SO → hapus permanen; ada riwayat SO → nonaktif (SO tetap tersimpan, bisa diaktifkan via **Aktifkan** di baris yang sama); akun `admin` tidak bisa dihapus atau dinonaktifkan.
  - Cadangan: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
  - Cadangan CLI (break-glass): `cd scripts; python create_user.py <username> <password>`.
- Rak: tabel `racks` di Table Editor.
- Hasil rak ini (kartu hasil rak): karyawan bisa menghapus entri yang **belum di-upload** (mis. produk ternyata sudah dihitung di rak lain) — datanya dibuang jadi tidak ikut ter-upload. Entri yang **sudah** di-upload terkunci, tidak bisa dihapus dari app; perbaikannya dilakukan langsung di baris tab Log.
- Spec & plan: `docs/superpowers/`.
