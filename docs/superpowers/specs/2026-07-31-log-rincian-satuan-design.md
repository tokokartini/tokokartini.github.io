# Log menyimpan rincian satuan asli

Tanggal: 2026-07-31
Status: disetujui, siap dibuatkan rencana implementasi

## Masalah

Sejak 2026-07-30 tab Log menyimpan satu baris per entri dalam satuan dasar saja
(`qty_total`). Satuan yang benar-benar diketik petugas — misalnya "2 krtn, 3
pack, 5 pcs" — hilang begitu entri di-upload. Saat hasil SO dicek ulang ke rak,
tidak ada cara menelusuri angka 125 itu datang dari hitungan seperti apa, atau
siapa yang menghitung bagian mana.

## Yang dibangun

Tab Log mendapat satu kolom teks berisi rincian satuan asli. Kolom Qty dan
Satuan tetap berisi hasil konversi ke satuan dasar seperti sekarang, sehingga
seluruh tab output tetap menghitung dengan angka yang sama.

### Susunan kolom Log (9 kolom, dari 8)

| Kolom | Isi | Contoh |
|---|---|---|
| A | Waktu | `2026-07-31 10:01:22` |
| B | Staff | `rian` |
| C | Rak | `Rak 3` |
| D | Produk | `Anchor Cream Cheese` |
| E | **Rincian** (baru) | `2 Krtn + 3 Pack + 5 Pcs` |
| F | Qty (satuan dasar) | `125` |
| G | Satuan (dasar) | `Pcs` |
| H | ED | `2027-01-01` |
| I | SKU | `BHK-0011-3` |

SKU sengaja diletakkan paling belakang: kolom yang dibaca manusia berkumpul di
depan, sementara SKU tetap ada karena tab Template Olsera mewajibkan kolom `sku`
dan Rekap/Arsip mengelompokkan per SKU. Sheet ini tidak punya tab master, jadi
SKU tidak bisa dicari ulang dari nama produk.

### Format kolom Rincian

- Satu ruas per satuan yang qty-nya bukan nol, dipisah ` + `.
- Urut dari `mult` terbesar ke terkecil, jadi karton disebut lebih dulu.
- Entri yang seluruh satuannya nol menghasilkan teks kosong; barisnya tetap
  ditulis (qty 0 tetap tercatat, sesuai perilaku yang sudah ada).
- Nama satuan diambil apa adanya dari `variant` di master, tidak diseragamkan.

### Yang tidak berubah

- Isi tab Rekap, Template Olsera, Arsip Harian, dan Arsip Bulanan. Keempatnya
  hanya perlu digeser nomor kolom sumbernya.
- Web app dan tabel `count_entries`. Rincian disusun di Edge Function dari
  kolom `units` yang memang sudah dikirim.
- `index.ts`. Append memakai range terbuka `Log!A1:append`, jadi lebar 9 kolom
  mengikuti dengan sendirinya.
- `totalQty()` di `src/lib/convert.js` tetap satu-satunya penghitung qty dasar.

## Komponen

**`supabase/functions/upload-rak/rows.ts`** — tambah `rincianText(units)` yang
murni, lalu `buildLogRows` menyusun 9 kolom dengan urutan di atas. File ini
tetap bebas Deno dan jaringan supaya bisa diuji di laptop.

**`supabase/functions/upload-rak/rows.test.ts`** — kasus uji: multi-satuan
lengkap, satuan qty 0 dilewati, semua qty 0 menghasilkan teks kosong, urutan
mult besar ke kecil, entri tanpa satuan tetap dilewati seperti sekarang, dan
posisi kesembilan kolom.

**`scripts/setup_sheet.py`** — header Log baru, lalu geser nomor kolom di
`LOG_SRC`, `REKAP`, `TEMPLATE`, `ARSIP`, `ARSIP_BULANAN`.

**`scripts/add_arsip_bulanan.py`** — geser nomor kolom pada formula yang sama.

**`scripts/migrate_log_kolom.py`** (baru) — pindahkan baris Log lama ke susunan
baru. Kolom Rincian dikosongkan; riwayat lama memang tidak menyimpan satuan
asli. Pola mengikuti `convert_log_base_unit.py`: dry-run sebagai perilaku
bawaan, `--tulis` membuat tab backup lebih dulu, dan batal kalau isi Log berubah
di tengah jalan.

## Urutan pengerjaan

Kerjakan saat tidak ada yang sedang SO. Migrasi sheet dan deploy Edge Function
harus berdekatan: di antara keduanya, upload yang masuk masih memakai susunan
lama dan isinya akan melenceng kolom.

1. Ubah `rows.ts` + `rows.test.ts`, jalankan tes sampai hijau.
2. Migrasi Log — dry-run dulu, periksa hasilnya, baru `--tulis`.
3. Perbarui formula lewat `add_arsip_bulanan.py` dan `setup_sheet.py`.
4. Deploy Edge Function.
5. Uji ujung ke ujung: satu entri multi-satuan dari web app, upload, lalu
   periksa satu baris di Log dan angka yang muncul di Rekap.

## Ketergantungan yang belum ada

Deploy Edge Function memerlukan `SUPABASE_ACCESS_TOKEN`; token lama sudah
dihapus. Tanpa token itu langkah 1–3 tetap bisa selesai, tetapi Edge Function
lama masih menulis 8 kolom ke Log 9 kolom, sehingga Rincian ikut terisi angka
qty dan seluruh kolom sesudahnya bergeser. Karena itu langkah 2 dan 3 jangan
dijalankan sebelum token tersedia.

## Risiko

**Baris ditulis dengan susunan lama.** Terjadi kalau ada upload di antara
migrasi dan deploy. Ditekan dengan mengerjakan di luar jam SO, dan tab backup
dari langkah migrasi menjadi jalan pulangnya.

**Formula meleset kolom.** Empat formula menunjuk nomor kolom Log secara
langsung. Diperiksa dengan menjalankan skrip setup yang memang sudah punya
assert atas hasil formula, bukan dengan membaca ulang formulanya.
