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

// Lokasi maya kedua, kebalikan dari SUPPLIER: penanda "barang keluar dari toko
// dan tidak balik". Bukan tempat, jadi TIDAK boleh ikut daftar lokasi yang punya
// saldo -- scripts/hitung_saldo.py membuangnya bersama SUPPLIER, kalau tidak dia
// muncul sebagai gudang palsu yang isinya menumpuk terus.
export const BUANG = 'Barang Rusak'

// Sebab barang keluar. 'Hilang' SENGAJA tidak ada: barang hilang ketahuan saat SO
// lewat selisih hitungan fisik, dan hitungan itu langsung jadi titik awal baru.
// Kalau disediakan di sini, orang memakainya untuk menutupi yang sebenarnya rusak
// dan angka kerugian jadi tidak bisa dibaca.
export const SEBAB = ['Rusak / pecah', 'Kadaluarsa', 'Dipakai toko sendiri']

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
    // Emoji, bukan simbol panah dua arah seperti U+21C4: simbol biasa cuma ada di
    // sebagian font sistem dan tampil kosong di HP yang tidak punya fontnya,
    // sementara emoji selalu punya font sendiri.
    ico: '🔀',
    sub: 'Geser stok antar gudang',
    kunci: null,
    tetap: '',
    tetapLabel: '',
    tetapIco: '',
    tanya: 'Dari gudang',
    nota: false,
    kecuali: [DISPLAY],
  },
  rusak: {
    key: 'rusak',
    jenis: 'Rusak',
    judul: 'Barang Rusak / Kadaluarsa',
    ico: '🗑',
    sub: 'Barang dibuang, stoknya berkurang',
    kunci: 'to',
    tetap: BUANG,
    tetapLabel: 'Tujuan',
    tetapIco: '🗑',
    tanya: 'Dibuang dari mana',
    nota: false,
    // Area Display ikut boleh: barang pajangan juga bisa rusak atau lewat ED.
    kecuali: [],
    // Satu-satunya jenis yang menuntut sebab.
    sebab: true,
  },
}

export const MODE_KEYS = ['display', 'datang', 'gudang', 'rusak']

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

// Sebab hanya sah untuk jenis Rusak, dan di jenis itu wajib. Aturannya dikunci di
// sini DAN di constraint movements_sebab_rusak: yang di sini supaya petugas dapat
// pesan yang bisa dibaca, yang di DB supaya baris salah tidak pernah bisa masuk
// lewat jalan lain (antrian offline, skrip, dashboard).
export function sebabSah(mode, sebab) {
  if (!mode.sebab) return !sebab
  return SEBAB.includes(sebab)
}

// Sebab yang boleh ikut disimpan untuk sebuah jenis. Jenis selain Rusak selalu
// mengirim '' supaya sebab tidak nyangkut waktu petugas berpindah jenis.
export function sebabUntuk(mode, sebab) {
  return mode.sebab ? sebab : ''
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
