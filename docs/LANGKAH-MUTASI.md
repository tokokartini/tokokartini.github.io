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

## Fase 2 — saldo per lokasi

| Lokasi | Rumus | Butuh Olsera | Skrip | Tab |
|---|---|---|---|---|
| Gudang | SO terakhir + datang + masuk − keluar | tidak | `scripts/hitung_stok.py` | Stok |
| Area Display | SO terakhir + isi ulang − keluar − penjualan | ya | `scripts/hitung_stok.py` | Stok |
| Pemeriksa | gudang + display = stok Olsera | ya | belum ada | — |

Semua skrip punya `--uji` yang jalan tanpa jaringan dan ikut dijalankan otomatis
sebelum menulis sheet, jadi sheet tak pernah ditulis dengan logika rusak.

Urutan jalannya untuk display:

```
export POS  ->  peta_satuan.py  ->  import_penjualan.py  ->  hitung_stok.py
                (tab Peta Satuan)   (tab Penjualan)          (tab Stok)
```

Sumber penjualan: export Olsera **Qty Produk Terjual** (rentang tanggal bebas),
contohnya di `~/Documents/Claude AI/Laporan Penjualan/katalog/`. Empat jebakan
yang sudah ditangani, semuanya dengan cara MELAPORKAN, bukan menebak:

1. `sales qty` per varian, bukan satuan dasar — 9 "Box (12 pcs)" = 108 Pcs.
   Konversinya lewat kolom Isi di tab Peta Satuan Olsera.
2. Sebagian baris `sku`-nya kosong (Almond Slice, Alu Cup, Alu Tray) — dicocokkan
   lewat nama + varian, dan yang tetap tidak ketemu tetap ditulis ke tab
   **Penjualan** dengan kolom **Sebab** terisi. Kalau dibuang diam-diam, saldo display
   kelihatan lebih banyak dari kenyataan dan tak ada yang tahu sebabnya.
3. Export per rentang, bukan per hari. Rentang yang **melintasi** hari SO display
   (mulai sebelum, berakhir sesudah) tidak dihitung sama sekali — sebagiannya
   sudah tercermin di hasil hitungan fisik dan tak ada cara memisahkannya. Baris
   begitu diberi catatan di tab Stok Display supaya ketahuan belum lengkap.
4. Kalau Area Display belum pernah di-SO, kolom Sisa **dikosongkan**. Tanpa titik
   awal, `isi ulang − penjualan` bukan sisa stok, cuma selisih.

Sisa display **boleh minus** dan minus itu sinyal, bukan bug: ada barang laku yang
isi ulangnya tidak pernah dicatat. Jangan pernah dipaksa jadi 0.

Selisih antara perkiraan dan hitungan fisik ada di tab **Selisih SO**
(`scripts/selisih_so.py`).

Yang belum digarap: tab Pemeriksa (`gudang + display` lawan stok POS) dan daftar
"Isi Ulang Hari Ini" — keduanya menunggu POS baru.
