# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Functions:
  - `upload-rak` → Google Sheet "SO Toko Kartini":
    - **Log** = sumber data satu-satunya; jangan dihapus isinya (baris 1 header juga).
    - **Rekap** & **Template Olsera** = satu hari sesuai kotak tanggal di `Rekap!G1` (kosong = hari ini).
    - **Arsip Harian** = semua hari.
  - `admin-create-user` → bikin akun staff dari halaman admin.
- Sync produk dari Master Pricelist: `cd scripts; python sync_products.py`.
- Setup spreadsheet: `cd scripts; python setup_sheet.py` (aman diulang; tidak menulis ke Log jika sudah ada data).
- Akun staff: login sebagai `admin` → buka halaman Admin (dashboard + form buat akun), isi username & password.
  - Hapus/nonaktifkan akun: tanpa riwayat SO → hapus permanen; ada riwayat SO → nonaktif (SO tetap tersimpan); akun `admin` tidak bisa dihapus.
  - Cadangan: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
  - Cadangan CLI (break-glass): `cd scripts; python create_user.py <username> <password>`.
- Rak: tabel `racks` di Table Editor.
- Spec & plan: `docs/superpowers/`.
