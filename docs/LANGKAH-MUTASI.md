# Mutasi barang — langkah yang tersisa

Kode fase 1 sudah selesai di branch `fitur-mutasi` (commit `34ebcc1`). Tab sheet
sudah dibuat dan formulanya sudah diuji. Yang tersisa di bawah ini butuh kamu.

Urutannya jangan ditukar: DB dulu, function, baru merge. Kalau `main` di-merge
lebih dulu, karyawan dapat menu Pengeluaran yang tabelnya belum ada.

---

## 1. Buat tabel `movements` (2 menit)

Supabase Dashboard → SQL Editor → tempel isi `supabase/migration-mutasi.sql` → Run.

Tidak menyentuh `count_entries`, `products`, `racks`, atau akun. Hanya menambah
satu tabel baru, tiga indeks, dan empat policy RLS.

Cek berhasil: Table Editor harus memuat tabel `movements` yang masih kosong.

---

## 2. Deploy Edge Function `upload-mutasi` (5 menit)

Butuh token yang belum ada di laptop. Ambil di Supabase Dashboard → Account →
Access Tokens → Generate new token.

**Jangan tempel token ke berkas mana pun — repo ini publik.** Cukup di terminal:

```bash
cd ~/Documents/"Claude AI"/so-kartini
export SUPABASE_ACCESS_TOKEN='<tempel token di sini>'
npx supabase functions deploy upload-mutasi --project-ref qfqulgkpbjceizrapyom --use-api
```

Function ini memakai secret yang sudah terpasang untuk `upload-rak`
(`GOOGLE_SA_EMAIL`, `GOOGLE_SA_KEY`, `SHEET_ID`) — tidak ada secret baru.

Ingat: `deploy.yml` **tidak** ikut men-deploy Edge Function, cuma GitHub Pages.
Jadi langkah ini memang harus manual, dan harus dilakukan sebelum merge.

---

## 3. Uji di HP sebelum merge (10 menit)

```bash
npm run dev
```

Buka dari HP di jaringan yang sama, login akun biasa (bukan `admin`), lalu:

1. **Isi Ulang Display** → pilih gudang → cari produk → isi jumlah → Simpan.
2. Tambah satu produk lagi, lalu hapus salah satunya dengan tombol 🗑.
3. Tekan **Kirim**. Harus muncul "N barang tercatat sebagai Isi Ulang."
4. Cek tab **Mutasi** di sheet: barisnya masuk, 11 kolom terisi.
5. Cek tab **Rekap Mutasi**: tergabung per SKU, tanggal terbaru di atas.
6. **Barang Datang** → isi nota → kirim → kolom Nota di sheet harus terisi.
7. Buka **Hitung Stok** sekali, pastikan alur SO masih sama seperti biasa.

Kalau ada baris uji coba yang ikut masuk, hapus manual dari tab Mutasi.
Jangan hapus baris judul.

---

## 4. Merge ke `main`

Sebelum merge, pastikan tidak ada SO yang sedang berjalan:

Table Editor → `count_entries` → filter `uploaded_at is null`. Kalau ada isinya,
tunggu sampai kosong.

```bash
git checkout main
git merge fitur-mutasi
git push
```

Push ke `main` memicu deploy GitHub Pages otomatis. Sekitar 2 menit kemudian
tampilan depan karyawan berubah jadi menu — **kabari mereka dulu** supaya tidak
kaget di tengah pekerjaan.

---

## Kalau ada yang salah setelah merge

Balikkan tampilan tanpa menghapus apa pun:

```bash
git revert --no-edit HEAD
git push
```

Tabel `movements` dan tab sheet boleh ditinggal — keduanya tidak dibaca alur SO,
jadi tidak mengganggu apa pun kalau menganggur.

---

## Fase 2 — belum digarap

Saldo per lokasi dan daftar isi ulang harian. Rumusnya:

| Lokasi | Rumus | Butuh Olsera |
|---|---|---|
| Gudang | SO terakhir + datang + masuk − keluar | tidak |
| Area Display | SO terakhir + isi ulang − penjualan | ya |
| Pemeriksa | gudang + display = stok Olsera | ya |

Sumber penjualan: export Olsera **Qty Produk Terjual** (rentang tanggal bebas).
Tiga jebakan yang sudah dicek di file contoh
`~/Documents/Claude AI/Laporan Penjualan/katalog/`:

1. `sales qty` per varian, bukan satuan dasar — 9 "Box (12 pcs)" = 108 Pcs.
   Konversinya pakai `mult` di tabel `products`, jangan dihitung ulang.
2. Sebagian baris `sku`-nya kosong (Almond Slice, Alu Cup, Alu Tray) — cocokkan
   lewat nama + varian, dan yang tetap tidak ketemu **dilaporkan**, jangan
   dibuang diam-diam. Kalau dibuang, saldo display kelihatan lebih banyak dari
   kenyataan.
3. Export per rentang, bukan per hari — saldo display akurat sampai export
   terakhir saja.

Garap fase 2 setelah fase 1 terbukti benar-benar diisi karyawan.
