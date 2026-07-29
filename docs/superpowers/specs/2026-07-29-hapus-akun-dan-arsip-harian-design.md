# Desain: Hapus Akun + Output Spreadsheet Per Hari — SO Kartini

Tanggal: 2026-07-29
Status: disetujui Sopian (sesi 2026-07-29, lanjutan [halaman admin](2026-07-29-admin-dashboard-design.md))

## Tujuan

1. Admin bisa menghapus/menonaktifkan akun karyawan dari halaman admin.
2. Output spreadsheet dipisah per hari SO (SO berjalan 3–5 hari di akhir bulan; tiap malam hasil hari itu ditarik ke Olsera), dengan arsip semua hari yang tidak hilang saat tanggal berganti.

## Keputusan produk

- **Hapus akun** ada di halaman admin (bukan hanya script/Dashboard).
- Perilaku hapus **bergantung riwayat**: akun tanpa entri SO dihapus permanen; akun yang sudah pernah input **dinonaktifkan** (tidak bisa login, entri SO utuh) dan bisa diaktifkan lagi.
- Akun `admin` tidak bisa dihapus/dinonaktifkan.
- Filter spreadsheet = **satu hari**, bukan rentang. Kotak tanggal kosong berarti hari ini.
- Kotak tanggal diletakkan di tab **Rekap**, bukan Template Olsera, supaya kolom A–G Template Olsera tetap bersih untuk di-copy ke Olsera.
- Arsip = tab baru **Arsip Harian**, rumus hidup dari Log (bukan salinan beku). Tidak perlu ditekan apa pun.

## Bagian 1 — Hapus akun

### Edge Function `admin-create-user`

Menambah dua action pada function yang sudah ada (tetap hanya menerima `admin@tokokartini.app`):

| Action | Perilaku |
|---|---|
| `list` (diubah) | Ikut mengembalikan status nonaktif tiap akun (`banned`) |
| `deactivate` (baru) | Hitung entri milik user. 0 entri → hapus permanen (`deleteUser`). >0 entri → nonaktifkan (`ban_duration` 100 tahun). Menolak `admin@tokokartini.app`. |
| `reactivate` (baru) | Aktifkan kembali (`ban_duration: 'none'`) |

Frontend mengirim `username`; function yang meresolusi ke user — UUID tidak pernah dikirim ke browser.

Response: `{ok:true, mode:'deleted'|'banned', username, entries}` atau `{ok:false, error}`.

### Halaman admin

Tiap baris di "Akun terdaftar" mendapat tombol:

- Akun normal → **Hapus** (dengan konfirmasi yang menyebut kedua kemungkinan hasilnya).
- Akun nonaktif → label `nonaktif` + tombol **Aktifkan**.
- Akun `admin` → tanpa tombol.

Setelah aksi berhasil, daftar akun dimuat ulang dan pesan hasil ditampilkan (mis. "Akun sari dinonaktifkan — 12 entri SO tetap tersimpan").

## Bagian 2 — Output per hari + arsip

Tab **Log** tetap satu-satunya sumber data (append-only oleh Edge Function `upload-rak`). Semua tab lain hanya menghitung ulang darinya.

### Kontrol tanggal

`Rekap!F1` = label `Tanggal (kosong = hari ini)`, `Rekap!G1` = nilai tanggal (kosong secara default).
Tanggal efektif = `IF(G1="";TODAY();G1)`, diformat `yyyy-mm-dd` untuk dicocokkan ke `Log!A` (teks `YYYY-MM-DD HH:MM:SS`).

### Tab yang terpengaruh

| Tab | Isi | Sumber |
|---|---|---|
| **Template Olsera** | Satu hari (tanggal efektif), agregat per SKU+rak. Kolom A–G tetap, siap ditarik ke Olsera | QUERY Log dengan `Col1 starts with '<tanggal>'` |
| **Rekap** | Satu hari, total qty per SKU, untuk pengecekan cepat | FILTER + SUMIFS dengan awalan tanggal |
| **Arsip Harian** (baru) | **Semua hari**, urut tanggal terbaru dulu: Tanggal \| SKU \| Produk \| Satuan \| Total Qty | QUERY atas `{LEFT(Log!A;10) , Log!D:G}` dikelompokkan per tanggal+SKU |

### Konsekuensi yang disepakati

Menghapus baris di Log menghapus hari itu dari semua tab sekaligus — tidak ada salinan lain. Baris 1 (judul) tidak boleh dihapus. Setelah SO beneran mulai, Log tidak boleh dihapus isinya.

## Testing

- Rumus sheet diverifikasi langsung terhadap data yang ada di sheet (data test 2026-07-27 masih ada saat pengerjaan): isi kotak tanggal `2026-07-27` → tiga tab terisi; kosongkan → Rekap & Template Olsera kosong (hari ini bukan 27), Arsip Harian tetap menampilkan 27.
- `scripts/setup_sheet.py` dibuat aman dijalankan ulang: uji-tulis ke Log hanya dilakukan bila Log kosong; bila sudah ada data, uji dilewati (tidak menimpa baris 2).
- Hapus/nonaktifkan akun diuji lewat script Node terhadap Supabase live: akun tanpa entri terhapus, akun dengan entri jadi nonaktif dan gagal login, reactivate mengembalikan login, akun `admin` ditolak, non-admin ditolak 403.

## Di luar cakupan

- Rentang tanggal (multi-hari) pada Template Olsera.
- Arsip beku/snapshot terpisah dari Log.
- Reset password dari web.
- Pemindahan Log lama ke sheet arsip terpisah (nanti kalau Log sudah kepanjangan).
