# Sheet output "SO Toko Kartini"

Sheet id `1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw`, milik Sopian, dishare ke
service account `point-coffee@claude-code-powershel.iam.gserviceaccount.com`.
Locale `in_ID`, jadi formula pakai `;` dan `\`. Zona Asia/Jakarta.

## Tab dan asalnya

| Tab | Diisi oleh | Sumber |
|---|---|---|
| **Log** | Edge Function `upload-rak` | hasil SO dari aplikasi |
| **Mutasi** | Edge Function `upload-mutasi` | barang datang / isi ulang / pindah gudang |
| Rekap | formula | Log, ikut kotak tanggal `Rekap!G1` |
| Template Olsera | formula | Log, siap impor POS |
| Arsip Harian | formula | Log, semua hari |
| Arsip Bulanan | formula | Log, semua bulan |
| Rekap Mutasi | formula | Mutasi |
| **Kadaluarsa** | formula | Log kolom ED + VLOOKUP ke Harga |
| **Ringkasan** | formula | semua tab di bawah ini |
| **Harga** | `scripts/harga_master.py` | Master Pricelist |
| Stok Gudang | `scripts/hitung_saldo.py` | Log + Mutasi + Harga |
| Stok Display | `scripts/saldo_display.py` | Log + Mutasi + Penjualan + Harga |
| **Arsip Saldo** | dua skrip saldo | potret harian, tidak pernah ditimpa habis |
| Peta Satuan Olsera | `scripts/peta_satuan.py` | export Olsera |
| Penjualan / Penjualan Tak Cocok | `scripts/import_penjualan.py` | export Olsera + Peta Satuan |

Log adalah satu-satunya sumber hasil SO. **Jangan pernah menulis ke Log dengan
skrip** kecuali benar-benar terpaksa: upload yang mendarat di tengah baca-tulis
pernah hilang permanen (7 entri, 2026-07-30).

## Menjalankan ulang

Otomatis tiap malam **03.30 WIB** lewat repo privat
[`tokokartini/so-kartini-jadwal`](https://github.com/tokokartini/so-kartini-jadwal):
`harga_master.py` → `hitung_saldo.py` → `saldo_display.py`.

Manual, tiga jalan:

1. Halaman admin aplikasi → tombol **🧮 Hitung saldo stok** (butuh secret
   `GITHUB_TOKEN` di Supabase, lihat di bawah)
2. GitHub → repo `so-kartini-jadwal` → Actions → *Hitung saldo* → Run workflow
3. Dari laptop: `cd scripts && python3 -u hitung_saldo.py`

Workflow-nya mengambil skrip dari repo aplikasi tiap kali jalan, jadi **tidak ada
salinan kode kedua** yang bisa berbeda. Python tetap satu-satunya sumber kebenaran
angka stok — itu sebabnya Edge Function `hitung-saldo` cuma memicu, tidak menghitung.

Yang TIDAK ikut jadwal: `peta_satuan.py` dan `import_penjualan.py` (butuh berkas
export yang diunduh manual), serta `add_*.py` (sekali pasang).

## Sekali pasang

```
python3 -u add_kadaluarsa.py     # tab Kadaluarsa
python3 -u add_ringkasan.py      # tab Ringkasan  (--uji untuk memeriksa angkanya)
python3 -u add_proteksi.py       # peringatan di 13 rentang formula
```

`add_proteksi.py` memakai `warning_only`, bukan kunci keras — kunci keras bisa
mengunci Sopian dari sheet miliknya sendiri. `--daftar` melihat yang terpasang,
`--lepas` melepas.

## Yang masih perlu dikerjakan orang

- **`GITHUB_TOKEN` di Supabase** supaya tombol admin hidup. Bikin fine-grained PAT
  yang cuma boleh mengakses repo `so-kartini-jadwal`, izin **Contents: Read and
  write**, lalu pasang:
  `npx supabase secrets set GITHUB_TOKEN=<token> --project-ref qfqulgkpbjceizrapyom`
- **Tab Pemeriksa** (`gudang + display` lawan stok POS) — nunggu POS baru.
- Katalog POS baru sebaiknya menyalin **nama produk, nama satuan, dan SKU** persis
  dari master. Kalau sama, tab Peta Satuan Olsera tidak diperlukan lagi.
