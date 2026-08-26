# Sheet output "SO Toko Kartini"

Sheet id `1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw`, milik Sopian, dishare ke
service account `point-coffee@claude-code-powershel.iam.gserviceaccount.com`.
Locale `in_ID`, jadi formula pakai `;` dan `\`. Zona Asia/Jakarta.

## Keadaan sekarang: 14 tab

Dikosongkan jadi 4 tab **25 Agustus 2026 sore** atas permintaan Sopian ("udah
pusing kemana-mana"): enam tab dibuat dalam sehari, dua langsung dibuang, sisanya
bikin sheet jadi susah dibaca. Dibangun ulang **26 Agustus 2026** — kali ini
sebagai satu rantai utuh, bukan tab lepas-lepas, karena Sopian minta alurnya
dibereskan sebelum SO pertama.

Urutan tabnya menurut cara pakai: yang dibaca di depan, sumber mentah di belakang.

| # | Tab | Diisi oleh | Isinya |
|---|---|---|---|
| 1 | **Ringkasan** | formula | keadaan hari ini: nilai stok, selisih, ED, kerugian, progres SO |
| 2 | **Cari Barang** | formula | ketik nama/SKU di `B1` → stok tiap lokasi, harga, ED, mutasi, selisih |
| 3 | **Stok** | `hitung_stok.py` | sisa semua lokasi, gudang dan Area Display jadi satu tabel |
| 4 | **Stok per Gudang** | formula | tabel silang: barang jadi baris, gudang jadi kolom |
| 5 | **Selisih SO** | `selisih_so.py` | perkiraan lawan hitungan fisik tiap SO |
| 6 | **Penjualan** | `import_penjualan.py` | penjualan POS per hari + status bayar, dari tabel `penjualan_harian` |
| 7 | **Barang Masuk** | formula | kiriman supplier + siapa yang bawa, dari Mutasi jenis Datang |
| 8 | **Barang Rusak** | formula | yang hangus + nilainya, dikelompokkan per sebab |
| 9 | **Kadaluarsa** | formula | barang mendekati ED, terdekat di atas |
| 10 | **Arsip Harian** | formula | hasil akhir SO per tanggal + SKU, satuan terkecil |
| 11 | **Riwayat SO** | formula | hasil SO tiap bulan, bulan terakhir dipecah per gudang |
| 12 | **Log** | Edge Function `upload-rak` | sumber: hasil SO mentah |
| 13 | **Mutasi** | Edge Function `upload-mutasi` | sumber: barang datang / isi ulang / pindah / rusak |
| 14 | **Harga** | `harga_master.py` | HPP + harga jual per SKU dari Master Pricelist |

**Tab `Mutasi` tidak boleh dihapus** — Edge Function `upload-mutasi` menulis ke
situ; tanpa tabnya, menu Pengeluaran di aplikasi langsung gagal.

## Alurnya

```
WEB APP  ──SO per gudang──────────►  Log
         ──Datang / Isi Ulang ────►  Mutasi
           Pindah Gudang / Rusak

MASTER PRICELIST ─────────────────►  Harga
EXPORT POS  ──upload halaman admin──►  penjualan_harian (Supabase) ─►  Penjualan

  Log + Mutasi + Harga ───────────►  Stok             sisa = SO terakhir + masuk − keluar
      + Penjualan (Area Display saja)
                          Stok ───►  Stok per Gudang  tabel silang
  Log + Mutasi + Harga ───────────►  Selisih SO       perkiraan lawan hitungan fisik
  Log kolom ED + Harga ───────────►  Kadaluarsa
  Mutasi jenis Datang ────────────►  Barang Masuk
  Mutasi jenis Rusak + Harga ─────►  Barang Rusak
  Log ────────────────────────────►  Arsip Harian, Riwayat SO

  semua di atas ──────────────────►  Ringkasan, Cari Barang
```

Tiap gudang punya titik nolnya sendiri: `sisa` dihitung dari **waktu SO gudang itu
saja**, jadi gudang tidak perlu di-SO serentak. Mutasi yang terjadi **sebelum** SO
sengaja diabaikan — waktu hitung fisik, transfer kemarin sudah ikut terhitung di
tumpukan, kalau dihitung lagi jadi dobel. Pindah antar gudang tercatat dua kali:
keluar di gudang asal, masuk di gudang tujuan, total dua gudang tetap.

Sisa boleh MINUS. Itu alarm mutasi yang lupa dicatat — jangan dipaksa jadi 0.

## URUTAN BANGUN ULANG — wajib, bukan saran

```
harga_master.py  →  import_penjualan.py  →  hitung_stok.py  →  add_stok_gudang.py
                 →  selisih_so.py
                 →  add_kadaluarsa.py  →  add_barang_masuk.py  →  add_barang_rusak.py
                 →  add_ringkasan.py  →  add_cari_barang.py
```

**Tab yang diacu HARUS sudah ada sebelum tab yang mengacu dibuat.** Google Sheets
tidak menunggu: begitu formula menyebut tab yang belum ada, acuannya ditulis ulang
jadi `#REF!` **permanen di dalam formula itu** — membuat tabnya belakangan tidak
memperbaiki apa pun.

Kena 26 Agu: `add_ringkasan.py` dijalankan sebelum `add_barang_rusak.py`. Blok
KERUGIAN BARANG dibungkus `IFERROR(...;0)` jadi galatnya tidak kelihatan — Ringkasan
melaporkan **"Barang rusak bulan ini: 0"** padahal ada 1 baris senilai Rp 10.500.
Gagal diam-diam, persis kelas yang sama dengan `ARRAYFORMULA(SUMIFS(...))` dan
kolom waktu bertipe teks. Obatnya cuma jalankan ulang skrip tab yang mengacu.

Kalau ragu tab mana yang mengacu ke mana:

```bash
grep -oE "\\?'[A-Z][a-zA-Z ]+\\?'!" scripts/add_*.py   # acuan bertanda kutip
grep -oE "(Stok|Harga|Log|Mutasi|Kadaluarsa)!" scripts/add_*.py
```

Acuan bertanda kutip (`'Barang Rusak'!`) TIDAK ketangkap pola tanpa kutip — dua-duanya
harus dicek.

## Tab yang masih dibongkar — skripnya utuh, belum dipasang

| Tab | Dibangun oleh | Isinya | Kenapa ditahan |
|---|---|---|---|
| **Peta Satuan Olsera** | `peta_satuan.py <export.xlsx>` | terjemahan satuan POS → master | dihapus 25 Agu; tak perlu lagi kalau katalog POS baru menyalin satuan master persis |

## Penjualan: dari POS sampai sisa display

Sejak 26 Agu 2026 penjualan masuk lewat **halaman admin aplikasi**, bukan skrip di
laptop. Export yang dipakai **`Item Penjualan berdasarkan Tanggal`** — bukan
`Qty Produk Terjual` yang lama.

Bedanya menentukan: export ini punya kolom `item sku`, dan SKU itu sudah menyebut
produk SEKALIGUS satuannya (`PKG-0053-G` Krtn, `-2` Pack, `-3` Pcs). Diukur pada
export 17–23 Agu 2026: **668 dari 673 SKU cocok, 99,3%**, omzet tak tercakup
Rp 103.400 dari Rp 107 juta. Export lama tidak punya kolom itu, jadi dulu harus
dicocokkan lewat nama + satuan — dan dari situlah tab `Peta Satuan Olsera` dengan
ratusan baris terjemahan manualnya lahir. Masalahnya jenis export, bukan katalog.

Alurnya:

1. Admin pilih berkas di halaman admin. **Browser memotong 69 kolom jadi 9** —
   email karyawan, nomor HP + alamat pelanggan, HPP, profit, dan komisi tidak
   pernah dikirim ke mana pun. Pembacanya `src/lib/parsePenjualan.js` (fflate +
   XML, bukan SheetJS: versi npm-nya basi dan ~900KB untuk PWA lewat kuota).
2. Layar menampilkan rentang tanggal, jumlah baris, omzet, piutang, dan berapa
   baris tanpa SKU **sebelum** disimpan. Wajib: kiriman ini MENGGANTI seluruh
   baris untuk tanggal di dalamnya, jadi berkas salah pilih bisa menghapus
   penjualan sebulan.
3. `ganti_penjualan()` di Postgres — satu fungsi, satu transaksi, hapus-lalu-isi
   tidak bisa terpisah. Mengganti, bukan menambah: transaksi yang dibatalkan di
   POS ikut hilang, dan upload ulang berkas yang sama tidak menggandakan apa pun.
4. `import_penjualan.py` membaca tabel + `products` (kolom `mult`) lalu menulis
   tab **Penjualan** dalam satuan dasar master.
5. `hitung_stok.py` mengurangkannya dari Area Display saja — POS tidak pernah
   menjual dari gudang.

**Sehari sekali cukup.** Sekali sebulan pilih rentang sebulan supaya tempo yang
sudah dibayar ikut terbarui: status `A` (belum bayar) berubah jadi `Z` di baris
tanggal transaksi ASLINYA, dan tidak ada kolom yang mencatat kapan dibayar. Kalau
cuma tanggal kemarin yang pernah dibaca, piutang menggelembung selamanya.

**TEMPO tetap mengurangi stok.** Barangnya sudah dibawa pelanggan, cuma bayarnya
belakangan (`posting time` terisi di semua baris). Di contoh sepekan itu Rp 13,2
juta dari tiga pelanggan.

**Penjualan pada HARI SO tidak dihitung**, dan itu disengaja: SO punya jam,
penjualan cuma punya tanggal, jadi tidak ada cara memisahkan yang laku sebelum
barangnya dihitung dari yang sesudah. Dilaporkan per produk di kolom Catatan,
bukan dibuang diam-diam.

**Baris yang gagal dicocokkan tetap ditulis** dengan kolom Sebab terisi. Di export
contoh ada 39 baris tanpa SKU senilai Rp 915.500 ("kertas nasi roll", "duo 40
hitam") — barang yang terjual tapi stoknya tidak dilacak siapa pun. Itu daftar
kerja, bukan sampah.

Tanpa tab `Penjualan`, kolom **Terjual** di tab Stok untuk Area Display selalu 0
dan sisa display cuma `SO + isi ulang − keluar`.

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

**Jadwal malam HIDUP lagi sejak 26 Agu 2026**, `30 20 * * *` UTC = **03.30 WIB**,
setengah jam sesudah sync produk. Sempat dimatikan 25 Agu karena ketiga skrip
MEMBUAT tabnya kalau belum ada — jadwal yang hidup akan memunculkan lagi
Harga/Stok/Selisih SO dan membatalkan pengosongan sheet tanpa ada yang sadar.
**Kalau sheet dikosongkan lagi, matikan jadwal ini duluan.**

### Google kadang balas 503

26 Agu 2026 sheet **Master Pricelist** membalas `APIError: [503]: The service is
currently unavailable.` untuk 2 dari 3 percobaan, sementara sheet SO di detik yang
sama sehat — jadi bukan kunci, izin, atau jaringan. Dua run workflow gagal
berturut-turut karena ini, dan karena `harga_master.py` langkah PERTAMA, satu 503
mematikan seluruh hitungan malam itu tanpa ada yang menonton Actions jam 03.30.

`scripts/google_ulang.py` membungkus `gspread.http_client.HTTPClient.request`:
ulang sampai 5 kali, jeda berlipat + jitter, untuk status 429/500/502/503/504.
Sudah dipasang di `harga_master.py`, `hitung_stok.py`, `selisih_so.py`.

**Yang sengaja TIDAK diulang**: 4xx lain (penolakan tetap — izin, id salah), dan
permintaan `addSheet` / `append` yang tidak idempoten, karena kalau permintaan
pertama ternyata mendarat lalu jawabannya yang hilang, ulangan bikin tab kembar
atau baris dobel. Sisanya aman diulang: skrip di sini selalu menulis ke rentang
tetap, jadi menulis hal yang sama dua kali hasilnya sama.

Kalau di log muncul `Google balas 503, ulang ke-2 sesudah 3.1 detik` lalu jobnya
sukses — itu tambalan ini bekerja, bukan masalah baru.

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

Urutannya penting — lihat **URUTAN BANGUN ULANG** di atas soal `#REF!` permanen.
Tab Harga dan tab Stok jadi sumber VLOOKUP tab-tab lain, jadi keduanya dulu, dan
`add_ringkasan.py` paling belakang karena mengacu ke paling banyak tab.

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
