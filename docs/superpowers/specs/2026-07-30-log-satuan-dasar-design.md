# Log satuan dasar — satu baris per entri

**Tanggal:** 2026-07-30
**Status:** disetujui user

## Masalah

Dua hal sekaligus.

**Pertama, `upload-rak` rusak.** Commit `708e71b` ("Update index.ts", diedit lewat GitHub web
2026-07-30 07:57 WIB) menyisipkan blok baru tanpa membuang blok lama: `const rows` dideklarasikan
dua kali, ada `for (const e of entries)` bersarang di dalam loop lama, dan kurung kurawalnya tidak
imbang (55 buka vs 54 tutup) — file itu tidak akan lolos parse. Yang menyelamatkan: `deploy.yml`
hanya men-deploy GitHub Pages, tidak men-deploy Edge Function, jadi yang aktif di Supabase masih
versi lama yang benar. Upload dari HP masih jalan selama versi rusak ini tidak pernah di-deploy.

**Kedua, format Log tidak seperti yang dimau.** Sekarang tiap satuan dapat barisnya sendiri:

```
2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Krtn (50 Pack)  KTN-0008-G   1
2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Pack            KTN-0008-3  25
```

Yang diinginkan satu baris saja per entri, dalam satuan dasar, qty totalnya:

```
2026-07-30 08:01:53  naruto  Rak 5  Kertas Nasi Putih MG 25*27  Pack            KTN-0008-3  75
```

Niat commit `708e71b` memang itu — hanya tulisannya kacau. Kolom `count_entries.qty_total` sudah
ada dan sudah diisi frontend lewat `totalQty()` di `src/lib/convert.js`, jadi datanya siap.

## Rancangan

### 1. `upload-rak` diperbaiki, logika baris dipisah

Commit rusak ditarik ke lokal apa adanya (bukan force-push), lalu diperbaiki di atasnya.

Pemilih baris pindah ke file murni `supabase/functions/upload-rak/rows.ts` — tanpa import Deno,
tanpa akses jaringan — sehingga bisa diuji Vitest langsung lewat `rows.test.ts`. Pola "kembaran"
seperti `parseMaster` tidak dipakai karena tidak ada salinan logika ini di `src/`.

`rows.ts` mengekspor:

- `wib(iso)` — geser +7 jam, format `YYYY-MM-DD HH:MM:SS` (dipindah dari `index.ts`)
- `baseUnitOf(units)` — `units.find(mult === 1)`, kalau tak ada ambil `mult` terkecil, `null` kalau kosong
- `buildLogRows(entries)` → `{ rows, skipped }`

Aturan baris:

| Hal | Keputusan |
|---|---|
| Satuan & SKU | dari satuan dasar (`mult === 1`), fallback `mult` terkecil |
| Qty | `Number(e.qty_total ?? 0)` |
| Qty 0 | tetap ditulis satu baris (keputusan lama, dipertahankan) |
| `units` kosong/null | entri dilewati, nama produknya masuk `skipped` → `console.warn` di `index.ts`; function tidak mati |
| `expired_date` null | ditulis `''` |
| Urutan baris | sama dengan urutan `entries` |
| Jumlah kolom | tetap 8: `Waktu, Staff, rack, Produk, Satuan, SKU, Qty, ED` |

Sisa `index.ts` tidak berubah: klaim atomik `uploaded_at`, rollback saat gagal, append
`insertDataOption=OVERWRITE` (INSERT_ROWS menggeser formula tab lain).

### 2. Konversi 168 baris Log yang sudah ada

Script sekali-pakai `scripts/convert_log_base_unit.py`:

1. Duplikat tab `Log` → `Log backup 2026-07-30`
2. Ambil `sku, product_name, variant, mult` dari tabel `products` (service key di `scripts/config.local.json`)
3. Grup baris per `(tanggal, staff, rak, produk)` → total = Σ(qty × mult) dalam satuan dasar
4. Tulis ulang `Log` sekali jalan, header tetap di baris 1
5. SKU yang tidak ada di `products` → barisnya dibiarkan apa adanya, dilaporkan di akhir

`Rekap`, `Template Olsera`, dan `Arsip Harian` tidak disentuh — ketiganya agregat per SKU di atas
`Log`, jadi ikut berubah sendiri. `Rekap!G1` tidak boleh tersentuh (`setup_sheet.py` mengosongkannya;
script ini tidak memanggilnya).

**Pengaman tabrakan:** Rak 5 masih punya ~377 entri terbuka. Kalau ada karyawan menekan upload saat
script menulis, baris baru mereka bisa tertimpa. Karena itu script mencatat jumlah baris terisi saat
membaca, membaca ulang tepat sebelum menulis, dan **berhenti tanpa menulis** kalau jumlahnya berubah.

### 3. Deploy

`npx supabase functions deploy upload-rak --project-ref qfqulgkpbjceizrapyom --use-api` butuh
`SUPABASE_ACCESS_TOKEN`. Token lama sudah dihapus, jadi perlu token baru dari user (Dashboard →
Account → Access Tokens). Sampai itu dilakukan, kode benar hanya duduk di repo dan Supabase tetap
menjalankan versi lama (format per-satuan).

Konsekuensi urutan: selama function belum di-deploy, upload baru tetap format lama. Jadi konversi
sheet sebaiknya dijalankan **setelah** deploy, atau diulang setelah upload terakhir hari itu.

## Testing

- `rows.test.ts` (Vitest): multi-satuan → 1 baris; tanpa `mult === 1` → `mult` terkecil; `qty_total`
  0/null → baris qty 0; `units` kosong → dilewati + masuk `skipped`; `expired_date` null → `''`;
  format `wib()`; urutan baris terjaga
- `npm test` — seluruh suite lama harus tetap hijau
- Konversi: dijalankan dengan backup tab lebih dulu; hasilnya dibandingkan manual di sheet sebelum
  backup dihapus

## Tambahan saat pengerjaan: tab Rekap ternyata salah hitung

Setelah konversi jalan, `Rekap` menulis 75 untuk dua SKU berbeda yang seharusnya 75 dan 22 —
sementara `Template Olsera` dan `Arsip Harian` benar. Sebabnya bukan konversi: kolom `Total Qty`
memakai `ARRAYFORMULA(IF(A2:A="";"";SUMIFS(...;Log!F:F;A2:A;...)))`, dan **`SUMIFS` tidak ter-vektor
di dalam `ARRAYFORMULA`** — tiap baris ikut hasil baris pertama. Diuji di tab sementara: `SUMIFS`
satu baris untuk `PKG-0094-3` mengembalikan 22 yang benar, jadi datanya memang tidak salah.

Bug ini ada sejak `setup_sheet.py` ditulis (2026-07-27) dan tidak pernah kelihatan karena tak ada
yang membandingkan angka Rekap dengan Log baris per baris.

Perbaikannya: keempat kolom Rekap diganti **satu** `QUERY` (pola yang sama dengan `Arsip Harian`,
yang sejak awal benar), lalu `B2:D2` dikosongkan:

```
=IFERROR(QUERY({Log!A2:H};"select Col6, Col4, Col5, sum(Col7)
 where Col6<>'' and Col1 starts with '"&<TGL>&"' group by Col6, Col4, Col5
 order by Col6 label sum(Col7) ''";0);"")
```

`setup_sheet.py` dan sheet live sudah sama-sama diperbarui. `Rekap!G1` tidak tersentuh (dicek
sebelum dan sesudah), dan kotak tanggalnya masih jalan: `2026-07-29` → 138 baris, kosong → hari SO
terakhir.

## Tambahan: awalan "STOK " di kolom produk tab output

Template import Olsera menuntut nama produk berawalan `STOK ` (kapital). Diminta user 2026-07-30.

Awalan ditambahkan **hanya di tab output** — `Template Olsera`, `Rekap`, `Arsip Harian`. Tab `Log`
tetap menyimpan nama produk asli supaya riwayat mentah masih bisa dicocokkan dengan master dan
dengan tabel `count_entries`; web app juga tidak berubah.

Caranya: kolom `Log!D` diganti kolom hitung di dalam sumber QUERY, sehingga nomor `Col` di semua
formula tidak bergeser:

```
PRODUK_STOK = ARRAYFORMULA(IF(Log!D2:D="";"";"STOK "&Log!D2:D))
LOG_SRC     = {Log!A2:C \ PRODUK_STOK \ Log!E2:H}
```

`Arsip Harian` memakai bentuk sendiri: `{ARRAYFORMULA(LEFT(Log!A2:A;10)) \ PRODUK_STOK \ Log!E2:G}`.

Diuji di tab sementara lebih dulu, lalu dipasang ke tab asli; qty tidak berubah (75 dan 22) dan
`Rekap!G1` tidak tersentuh.

## Di luar lingkup

Struktur tab lain, format kolom, dan kemampuan mengoreksi hasil dengan tangan di sheet. Penyebab
sync malam tidak jalan (tidak ada baris `sync_runs` untuk 03:00 WIB 2026-07-30) dicatat terpisah —
bukan bagian pekerjaan ini.
