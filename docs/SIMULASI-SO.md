# Latihan SO sebelum SO asli

Tujuannya bukan menghasilkan angka, tapi **menemukan yang rusak selagi masih boleh
rusak**. Kerjakan sehari sebelum SO asli, jangan di hari H.

Pakai satu tanggal khusus supaya gampang dibersihkan. Contoh di bawah pakai
`2026-08-26` — ganti dengan tanggal latihanmu.

---

## 0. Sebelum mulai

| Cek | Di mana | Harus |
|---|---|---|
| Produk sudah sync | halaman admin, kartu Produk | "terakhir sync" hari ini, tidak merah |
| Nama rak benar | halaman Home | 5 lokasi, termasuk **Area Display** |
| Harga sudah ditarik | tab **Harga** di sheet | 2705 baris, kolom HPP terisi |
| Sheet bersih | tab **Log** | 0 baris (kalau ada isinya, itu sisa yang belum dibersihkan) |

---

## 1. Hitung di satu gudang

Login sebagai satu karyawan biasa, **bukan admin**. Pilih satu gudang. Hitung
3–5 produk, sengaja pakai bentuk yang beda-beda:

1. **Multi-satuan** — satu produk isi dua kolom, mis. `1 Krtn` + `5 Pack`.
   Nanti di tab Log kolom **Rincian** harus tertulis apa adanya, sedangkan
   kolom Qty sudah jadi satuan dasar.
2. **Isi tanggal ED** di salah satu produk. Nanti muncul di tab **Kadaluarsa**.
3. **Satu produk qty 0.** Harus tetap tercatat, bukan hilang — itu artinya
   "sudah dicek, memang kosong".
4. **Hapus satu entri** pakai tombol 🗑, lalu tekan **Urungkan**. Entrinya harus
   balik utuh.

## 2. Coba tanpa sinyal

Masih di halaman hitung:

1. Nyalakan mode pesawat di HP.
2. Simpan satu hitungan → harus muncul tanda **"menunggu sinyal"**, bukan pesan
   gagal.
3. Muat ulang halaman selagi tetap tanpa sinyal → **tidak boleh** dilempar ke
   layar login, dan daftar hitungan harus masih ada.
4. Matikan mode pesawat → dalam sekitar 10 detik antrian harus kosong sendiri.

Kalau langkah 3 melempar ke login, berhenti dan laporkan — itu bug, bukan
kesalahan pemakaian.

## 3. Upload

Tekan Upload di bar bawah. Sesudah itu entri yang terkirim hilang dari daftar dan
pindah ke bagian buka-tutup "sudah terkirim".

## 4. **Ulangi di Area Display** ← jangan dilewat

Ini langkah yang paling sering terlupa. Tanpa SO Area Display, kolom **Sisa** di
tab Stok Display tetap kosong selamanya — bukan rusak, memang tidak ada titik
awalnya. Hitung 2–3 produk saja sudah cukup untuk latihan.

## 5. Mutasi barang

Buka halaman Pengeluaran, coba tiga-tiganya sekali masing-masing:

- **Barang Datang** → satu produk masuk ke satu gudang
- **Isi Ulang Display** → satu produk dari gudang ke Area Display
- **Pindah Antar Gudang** → satu produk antar dua gudang

## 6. Periksa sheet

Buka sheet, cocokkan:

| Tab | Yang harus kelihatan |
|---|---|
| **Log** | satu baris per produk per rak; kolom Rincian sesuai yang diketik |
| **Arsip Harian** | tanggal latihan muncul |
| **Kadaluarsa** | produk yang tadi diisi ED, dengan Sisa Hari + Nilai HPP |
| **Mutasi** | tiga baris dari langkah 5, kolom Jenis benar |
| **Barang Rusak** | yang dibuang, lengkap nilai rupiahnya |

## 7. Hitung saldo

Salah satu:

- halaman admin → **🧮 Hitung saldo stok** (kalau `GITHUB_TOKEN` sudah dipasang)
- GitHub → repo `so-kartini-jadwal` → Actions → *Hitung saldo* → Run workflow
- dari laptop: `cd scripts && python3 -u hitung_stok.py && python3 -u selisih_so.py`

Lalu periksa:

| Tab | Yang harus kelihatan |
|---|---|
| **Stok** | baris 1 berbunyi `✓ Terbaru`; sisa gudang = SO + masuk − keluar, kolom Nilai Sisa ada rupiahnya |
| **Stok** (Area Display) | isi ulang dari langkah 5 masuk kolom Masuk |
| **Selisih SO** | selisih antara perkiraan dan hitungan fisik |
| **Ringkasan** | nilai stok bukan Rp 0, "Area Display sudah di-SO?" = **sudah** |
| **Cari Barang** | ketik nama produk A, semua blok terisi |

Kalau ada baris tanpa harga, jalankan `python3 -u harga_master.py` lalu ulangi.

## 8. Bersihkan

**Wajib, sebelum SO asli.** Entri yang sudah ter-upload tidak bisa dihapus lewat
aplikasi.

```
cd scripts
python3 -u bersihkan_simulasi.py 2026-08-26            # lihat dulu apa yang kena
python3 -u bersihkan_simulasi.py 2026-08-26 --tulis    # baru hapus
python3 -u hitung_stok.py && python3 -u selisih_so.py
```

Skrip itu membuang baris tab Log + Mutasi dan baris `count_entries` + `movements`
pada tanggal itu saja. Tab olahan ikut bersih sendiri karena semuanya formula.

Dua pengamannya: batal kalau masih ada entri yang belum di-upload (tandanya ada
yang sedang menghitung), dan baris Log dihapus satu per satu, bukan dengan menulis
ulang seluruh tab — penulisan ulang itu yang dulu menghilangkan 7 entri permanen.

Sesudah itu cek tab **Log** kembali 0 baris.

---

## Kalau ada yang aneh

Catat: **halaman apa, ditekan apa, muncul apa.** Jangan hapus datanya dulu —
data latihan yang rusak justru barang bukti yang paling berguna.
