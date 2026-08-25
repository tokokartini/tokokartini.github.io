# Sheet output "SO Toko Kartini"

Sheet id `1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw`, milik Sopian, dishare ke
service account `point-coffee@claude-code-powershel.iam.gserviceaccount.com`.
Locale `in_ID`, jadi formula pakai `;` dan `\`. Zona Asia/Jakarta.

**12 tab**, diurutkan menurut cara pakai — yang paling sering dibuka di depan,
sumber data di belakang supaya tidak kesenggol.

| # | Tab | Diisi oleh | Isinya |
|---|---|---|---|
| 1 | **Ringkasan** | formula | keadaan hari ini: nilai stok, selisih, ED, kerugian, progres SO per lokasi |
| 2 | **Cari Barang** | formula | ketik nama/SKU di `B1` → stok tiap lokasi, harga, ED, mutasi, selisih |
| 3 | **Stok per Gudang** | formula | tabel silang: barang jadi baris, gudang jadi kolom, plus blok total |
| 4 | **Stok** | `hitung_stok.py` | sisa semua lokasi, gudang dan Area Display jadi satu tabel (bentuk memanjang) |
| 5 | **Selisih SO** | `selisih_so.py` | perkiraan lawan hitungan fisik tiap SO |
| 6 | **Barang Rusak** | formula | yang hangus + nilainya, dikelompokkan per sebab |
| 7 | **Kadaluarsa** | formula | barang mendekati ED, terdekat di atas |
| 8 | **Arsip Harian** | formula | hasil akhir SO per tanggal + SKU, satuan terkecil |
| 9 | **Log** | Edge Function `upload-rak` | sumber: hasil SO mentah |
| 10 | **Mutasi** | Edge Function `upload-mutasi` | sumber: barang datang / isi ulang / pindah / rusak |
| 11 | **Harga** | `harga_master.py` | HPP + harga jual per SKU dari Master Pricelist |
| 12 | **Penjualan** | `import_penjualan.py` | penjualan POS per periode; baris ber-`Sebab` = gagal dikonversi |

Log dan Mutasi adalah satu-satunya sumber. **Jangan pernah menulis ke Log dengan
skrip** kecuali terpaksa: upload yang mendarat di tengah baca-tulis pernah hilang
permanen (7 entri, 2026-07-30).

## Yang jalan sendiri vs yang harus dijalankan

Tab formula (1, 2, 3, 6, 7, 8) selalu terbarui begitu ada upload. Tab skrip (4, 5)
tidak — dan itu bahaya diam-diam, jadi **baris 1 masing-masing berbunyi sendiri**:

```
✓ Terbaru — dihitung 25 Agu 15:29
⚠ ANGKA LAMA — dihitung 24 Agu 03:30, jalankan ulang hitung saldo
```

Judul tabelnya ada di baris 2, datanya mulai baris 3. Formula yang membaca kedua
tab itu harus mulai dari `A3`, bukan `A2`.

## Menjalankan ulang

Otomatis tiap malam **03.30 WIB** lewat repo privat
[`tokokartini/so-kartini-jadwal`](https://github.com/tokokartini/so-kartini-jadwal):
`harga_master.py` → `hitung_stok.py` → `selisih_so.py`.

Manual, tiga jalan:

1. Halaman admin aplikasi → tombol **🧮 Hitung saldo stok** (butuh secret
   `GITHUB_TOKEN` di Supabase, lihat di bawah)
2. GitHub → repo `so-kartini-jadwal` → Actions → *Hitung saldo* → Run workflow
3. Dari laptop: `cd scripts && python3 -u hitung_stok.py`

Workflow mengambil skrip dari repo aplikasi tiap kali jalan, jadi **tidak ada
salinan kode kedua** yang bisa berbeda. Python tetap satu-satunya sumber kebenaran
angka stok — itu sebabnya Edge Function `hitung-saldo` cuma memicu, tidak menghitung.

Yang TIDAK ikut jadwal: `peta_satuan.py` dan `import_penjualan.py` (butuh berkas
export yang diunduh manual), serta `add_*.py` (sekali pasang).

## Sekali pasang

```
python3 -u setup_sheet.py        # Log + Arsip Harian, untuk bangun ulang dari nol
python3 -u add_mutasi.py         # baris judul tab Mutasi
python3 -u add_kadaluarsa.py     # tab Kadaluarsa
python3 -u add_barang_rusak.py   # tab Barang Rusak
python3 -u add_cari_barang.py    # tab Cari Barang   (--uji mencoba cari barang sungguhan)
python3 -u add_stok_gudang.py    # tab Stok per Gudang (--uji cocokkan dengan tab Stok)
python3 -u add_ringkasan.py      # tab Ringkasan     (--uji memeriksa angkanya)
python3 -u add_proteksi.py       # peringatan di rentang formula
```

`add_proteksi.py` memakai `warning_only`, bukan kunci keras — kunci keras bisa
mengunci Sopian dari sheet miliknya sendiri. `--daftar` melihat yang terpasang,
`--lepas` melepas.

## Yang dibuang 2026-08-25, dan kenapa

| Tab | Alasan |
|---|---|
| Rekap | Arsip Harian yang disaring satu tanggal. Data sama, sudah difilter. |
| Template Olsera | untuk impor balik ke POS, tidak pernah dipakai. Yang dibutuhkan cuma hasil akhir satuan terkecil = Arsip Harian. |
| Arsip Bulanan | SO sebulan sekali, jadi barisnya sama persis dengan Arsip Harian. Duplikat. |
| Rekap Mutasi | mengagregat tab Mutasi yang sendirinya sudah satu baris per barang. Tidak menjawab pertanyaan apa pun. |
| Arsip Saldo | dibuat untuk jadi pembanding Selisih SO, ternyata Selisih SO menghitung langsung dari Log + Mutasi. Tidak dipakai apa pun. |
| Stok Gudang + Stok Display | digabung jadi tab Stok. Dua tab berarti dua kali buka untuk satu pertanyaan, dan bisa setengah terbarui. |
| Penjualan Tak Cocok | digabung ke Penjualan sebagai kolom Sebab. Tab terpisah yang tidak pernah dibuka sama saja dengan dibuang. |

Ikutan: awalan **`STOK `** di depan nama produk juga dibuang. Itu tuntutan template
impor Olsera; tanpa template, awalan itu cuma bikin nama di Arsip Harian tidak
cocok dengan tab Stok, Mutasi, dan Cari Barang.

Cadangan lengkap sebelum perombakan (17 tab CSV + `_formula.json`):
`~/Documents/Olsera/Stok/backup-sheet-2026-08-25/`

## Yang masih perlu dikerjakan orang

- **`GITHUB_TOKEN` di Supabase** supaya tombol admin hidup. Fine-grained PAT yang
  cuma boleh mengakses repo `so-kartini-jadwal`, izin **Contents: Read and write**:
  `npx supabase secrets set GITHUB_TOKEN=<token> --project-ref qfqulgkpbjceizrapyom`
- **Tab Pemeriksa** (`gudang + display` lawan stok POS) — nunggu POS baru.
- Katalog POS baru sebaiknya menyalin **nama produk, nama satuan, dan SKU** persis
  dari master. Kalau sama, tab Peta Satuan Olsera tidak diperlukan lagi.
