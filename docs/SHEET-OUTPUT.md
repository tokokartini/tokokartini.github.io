# Sheet output "SO Toko Kartini"

Sheet id `1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw`, milik Sopian, dishare ke
service account `point-coffee@claude-code-powershel.iam.gserviceaccount.com`.
Locale `in_ID`, jadi formula pakai `;` dan `\`. Zona Asia/Jakarta.

## Keadaan sekarang: 4 tab

Dikosongkan **25 Agustus 2026 sore** atas permintaan Sopian ("udah pusing
kemana-mana"): enam tab dibuat dalam sehari, dua langsung dibuang, sisanya bikin
sheet jadi susah dibaca. Sekarang dibangun ulang **satu per satu, sesudah jelas
tab itu dipakai** — bukan sekaligus.

| Tab | Diisi oleh | Isinya |
|---|---|---|
| **Log** | Edge Function `upload-rak` | sumber: hasil SO mentah |
| **Mutasi** | Edge Function `upload-mutasi` | sumber: barang datang / isi ulang / pindah / rusak |
| **Arsip Harian** | formula | hasil akhir SO per tanggal + SKU, satuan terkecil |
| **Riwayat SO** | formula | hasil SO tiap bulan, bulan terakhir dipecah per gudang |

**Tab `Mutasi` tidak boleh dihapus** — Edge Function `upload-mutasi` menulis ke
situ; tanpa tabnya, menu Pengeluaran di aplikasi langsung gagal.

## Tab yang dibongkar — skripnya masih utuh

Semua bisa dibangun ulang satu perintah. **Urutan wajib: `harga_master.py` dulu**,
banyak tab lain VLOOKUP ke tab Harga; sesudah itu `hitung_stok.py`, baru sisanya.

| Tab | Dibangun oleh | Isinya |
|---|---|---|
| **Harga** | `harga_master.py` | HPP + harga jual per SKU dari Master Pricelist |
| **Stok** | `hitung_stok.py` | sisa semua lokasi, gudang dan Area Display jadi satu tabel |
| **Selisih SO** | `selisih_so.py` | perkiraan lawan hitungan fisik tiap SO |
| **Ringkasan** | `add_ringkasan.py` | keadaan hari ini: nilai stok, selisih, ED, kerugian, progres SO |
| **Cari Barang** | `add_cari_barang.py` | ketik nama/SKU di `B1` → stok tiap lokasi, harga, ED, mutasi |
| **Stok per Gudang** | `add_stok_gudang.py` | tabel silang: barang jadi baris, gudang jadi kolom |
| **Barang Masuk** | `add_barang_masuk.py` | kiriman supplier, dari Mutasi jenis Datang |
| **Barang Rusak** | `add_barang_rusak.py` | yang hangus + nilainya, dikelompokkan per sebab |
| **Kadaluarsa** | `add_kadaluarsa.py` | barang mendekati ED, terdekat di atas |
| **Penjualan** | `import_penjualan.py` | penjualan POS per periode; baris ber-`Sebab` = gagal dikonversi |
| **Peta Satuan Olsera** | `peta_satuan.py <export.xlsx>` | terjemahan satuan POS → master; dihapus 25 Agu, POS Olsera mau habis |

Cadangan isi 16 tab sebelum dikosongkan (CSV + `_formula.json`):
`~/Documents/Olsera/Stok/backup-sheet-2026-08-25/`

Log dan Mutasi adalah satu-satunya sumber. **Jangan pernah menulis ke Log dengan
skrip** kecuali terpaksa: upload yang mendarat di tengah baca-tulis pernah hilang
permanen (7 entri, 2026-07-30).

## Yang jalan sendiri vs yang harus dijalankan

Tab formula (Ringkasan, Cari Barang, Stok per Gudang, Barang Masuk, Barang Rusak,
Kadaluarsa, Arsip Harian, Riwayat SO) selalu terbarui begitu ada upload. Tab skrip
(Harga, Stok, Selisih SO) tidak — dan itu bahaya diam-diam, jadi **baris 1
masing-masing berbunyi sendiri**:

```
✓ Terbaru — dihitung 25 Agu 15:29
⚠ ANGKA LAMA — dihitung 24 Agu 03:30, jalankan ulang hitung saldo
```

Judul tabelnya ada di baris 2, datanya mulai baris 3. Formula yang membaca kedua
tab itu harus mulai dari `A3`, bukan `A2`.

## Menjalankan ulang

Repo privat [`tokokartini/so-kartini-jadwal`](https://github.com/tokokartini/so-kartini-jadwal)
menjalankan `harga_master.py` → `hitung_stok.py` → `selisih_so.py`.

**Jadwal malamnya DIMATIKAN 25 Agu 2026** (baris `schedule` dikomentari). Wajib:
ketiga skrip itu MEMBUAT tabnya kalau belum ada, jadi jadwal yang dibiarkan hidup
akan memunculkan lagi Harga/Stok/Selisih SO jam 03.30 dan membatalkan pengosongan
tanpa ada yang sadar. Hidupkan lagi dengan membuang komentar SESUDAH jelas tab mana
yang dipakai.

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

Urutannya penting: tab Harga dan tab Stok jadi sumber VLOOKUP tab-tab lain, jadi
keduanya dulu.

```
python3 -u setup_sheet.py        # Log + Arsip Harian, untuk bangun ulang dari nol
python3 -u add_mutasi.py         # baris judul tab Mutasi
python3 -u harga_master.py       # tab Harga        — JALANKAN DULUAN
python3 -u hitung_stok.py        # tab Stok         — sesudah Harga
python3 -u selisih_so.py         # tab Selisih SO
python3 -u add_riwayat_so.py     # tab Riwayat SO
python3 -u add_barang_masuk.py   # tab Barang Masuk
python3 -u add_kadaluarsa.py     # tab Kadaluarsa
python3 -u add_barang_rusak.py   # tab Barang Rusak
python3 -u add_cari_barang.py    # tab Cari Barang   (--uji mencoba cari barang sungguhan)
python3 -u add_stok_gudang.py    # tab Stok per Gudang (--uji cocokkan dengan tab Stok)
python3 -u add_ringkasan.py      # tab Ringkasan     (--uji memeriksa angkanya)
python3 -u add_proteksi.py       # peringatan di rentang formula — paling akhir
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
- **Katalog POS baru**: salin **nama produk, nama satuan, dan SKU** persis dari
  master. Kalau sama persis, tab Peta Satuan Olsera memang tidak perlu dibuat lagi.
- **Export stok dari POS baru** — bahan tab Pemeriksa.
- **Tab Pemeriksa** (`gudang + display` lawan stok POS) dan daftar **"Isi Ulang
  Hari Ini"** — belum digarap; keduanya nunggu Area Display di-SO sekali dulu.
- **SO pertama sesudah reset**: rencana akhir Agustus 2026. Sebelum itu Log dan
  Mutasi hampir kosong, jadi tab hitungan apa pun akan nol — itu wajar, bukan bug.
  Pastikan **Area Display ikut dihitung**; tanpa titik awal itu kolom Sisa display
  memang sengaja dikosongkan.
