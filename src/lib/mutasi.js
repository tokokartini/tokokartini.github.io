// Aturan tiap jenis surat jalan. File murni (tanpa React/Supabase) supaya bisa
// diuji di laptop dan dipakai bareng halaman Keluar + hook useMovements.
//
// Tiap jenis mengunci sisi yang memang selalu sama. Isi ulang SELALU berakhir di
// Area Display, barang datang SELALU berasal dari supplier -- kalau kedua sisi
// dibiarkan bebas seperti versi pertama, petugas disodori dua daftar lokasi yang
// isinya sama persis dan harus mengingat sendiri mana yang benar.

export const DISPLAY = 'Area Display'

// Lokasi maya. Bukan baris di tabel `racks`, karena bukan tempat yang bisa dihitung
// waktu SO -- cuma penanda "barang ini masuk dari luar toko".
export const SUPPLIER = 'Barang Datang'

export const MODES = {
  display: {
    key: 'display',
    jenis: 'Isi Ulang',
    judul: 'Isi Ulang Display',
    ico: '📤',
    sub: 'Naikkan barang dari gudang ke display',
    kunci: 'to',
    tetap: DISPLAY,
    tetapLabel: 'Tujuan',
    tetapIco: '🏬',
    tanya: 'Ambil dari gudang',
    nota: false,
    // Display tidak boleh jadi asal: barang turun dari display ke gudang itu retur,
    // alurnya beda dan belum ada.
    kecuali: [DISPLAY],
  },
  datang: {
    key: 'datang',
    jenis: 'Datang',
    judul: 'Barang Datang',
    ico: '📥',
    sub: 'Kiriman supplier masuk gudang',
    kunci: 'from',
    tetap: SUPPLIER,
    tetapLabel: 'Asal',
    tetapIco: '🚚',
    tanya: 'Simpan ke mana',
    nota: true,
    // Display ikut boleh: kiriman yang langsung dipajang tanpa mampir gudang.
    kecuali: [],
  },
  gudang: {
    key: 'gudang',
    jenis: 'Pindah',
    judul: 'Pindah Antar Gudang',
    ico: '⇄',
    sub: 'Geser stok antar gudang',
    kunci: null,
    tetap: '',
    tetapLabel: '',
    tetapIco: '',
    tanya: 'Dari gudang',
    nota: false,
    kecuali: [DISPLAY],
  },
}

export const MODE_KEYS = ['display', 'datang', 'gudang']

export function modeOf(key) {
  return MODES[key] || MODES.display
}

// Lokasi yang boleh dipilih untuk satu sisi. `racks` datang dari tabel racks apa
// adanya, jadi lokasi baru cukup ditambah di DB tanpa menyentuh kode ini.
export function lokasiPilihan(mode, racks) {
  return racks.filter((r) => !mode.kecuali.includes(r))
}

// Nilai awal from/to saat sebuah jenis dipilih dari menu.
export function lokasiAwal(mode) {
  return {
    from: mode.kunci === 'from' ? mode.tetap : '',
    to: mode.kunci === 'to' ? mode.tetap : '',
  }
}

export function siapLanjut(from, to) {
  return Boolean(from) && Boolean(to) && from !== to
}

// Urutan produk di daftar "sering diisi ulang": paling sering dulu, lalu nama
// supaya urutannya tidak berubah-ubah sendiri saat frekuensinya seri.
export function seringDipakai(rows, batas = 8) {
  const hitung = new Map()
  for (const r of rows || []) {
    hitung.set(r.product_name, (hitung.get(r.product_name) || 0) + 1)
  }
  return [...hitung.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, batas)
    .map(([product_name, n]) => ({ product_name, n }))
}
