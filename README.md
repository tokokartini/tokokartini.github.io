# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Functions:
  - `upload-rak` → Google Sheet "SO Toko Kartini" (Log/Rekap/Template Olsera).
  - `admin-create-user` → bikin akun staff dari halaman admin.
- Sync produk dari Master Pricelist: `cd scripts; python sync_products.py`.
- Akun staff: login sebagai `admin` → buka halaman Admin (dashboard + form buat akun), isi username & password.
  - Cadangan: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
  - Cadangan CLI (break-glass): `cd scripts; python create_user.py <username> <password>`.
- Rak: tabel `racks` di Table Editor.
- Spec & plan: `docs/superpowers/`.
