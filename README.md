# Stok Opname Kartini

Web app stok opname Toko Kartini — https://tokokartini.github.io

- Frontend: React + Vite, GitHub Pages (deploy otomatis push main).
- Data: Supabase (`products`, `racks`, `count_entries`) + Edge Function `upload-rak` → Google Sheet "SO Toko Kartini" (Log/Rekap/Template Olsera).
- Sync produk dari Master Pricelist: `cd scripts; python sync_products.py`.
- Akun staff: Supabase Dashboard → Authentication → Add user, email `<username>@tokokartini.app`, centang auto-confirm.
- Rak: tabel `racks` di Table Editor.
- Spec & plan: `docs/superpowers/`.
