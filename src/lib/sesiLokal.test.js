import { describe, it, expect } from 'vitest'
import {
  bacaSesiLokal,
  hapusSesiLokal,
  kunciSesiServer,
  logoutSungguhan,
  lupakanSesiServer,
  pilihSesi,
  simpanSesiLokal,
} from './sesiLokal'

function storePalsu(awal = {}) {
  const map = new Map(Object.entries(awal))
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
    _map: map,
  }
}

const sesi = { access_token: 'rahasia', refresh_token: 'rahasia2', user: { id: 'u1', email: 'rian@tokokartini.app' } }

describe('sesiLokal', () => {
  it('menyimpan lalu mengembalikan identitas dengan penanda lokal', () => {
    const store = storePalsu()
    expect(simpanSesiLokal(sesi, store)).toBe(true)
    expect(bacaSesiLokal(store)).toEqual({ user: { id: 'u1', email: 'rian@tokokartini.app' }, lokal: true })
  })

  it('TIDAK ikut menyimpan token apa pun', () => {
    const store = storePalsu()
    simpanSesiLokal(sesi, store)
    const mentah = [...store._map.values()].join(' ')
    expect(mentah).not.toContain('rahasia')
    expect(mentah).not.toContain('rahasia2')
  })

  it('mengembalikan null kalau belum pernah login', () => {
    expect(bacaSesiLokal(storePalsu())).toBeNull()
  })

  it('menolak session tanpa id atau email', () => {
    const store = storePalsu()
    expect(simpanSesiLokal({ user: { id: 'u1' } }, store)).toBe(false)
    expect(simpanSesiLokal({ user: { email: 'a@b.c' } }, store)).toBe(false)
    expect(simpanSesiLokal(null, store)).toBe(false)
    expect(bacaSesiLokal(store)).toBeNull()
  })

  it('menganggap isi rusak sebagai belum login, bukan melempar', () => {
    expect(bacaSesiLokal(storePalsu({ 'so-sesi-v1': '{bukan json' }))).toBeNull()
    expect(bacaSesiLokal(storePalsu({ 'so-sesi-v1': '{"id":"u1"}' }))).toBeNull()
  })

  it('hapus bikin sesi berikutnya balik ke halaman login', () => {
    const store = storePalsu()
    simpanSesiLokal(sesi, store)
    hapusSesiLokal(store)
    expect(bacaSesiLokal(store)).toBeNull()
  })

  it('tidak melempar saat localStorage diblokir', () => {
    const buntu = {
      getItem: () => { throw new Error('diblokir') },
      setItem: () => { throw new Error('diblokir') },
      removeItem: () => { throw new Error('diblokir') },
    }
    expect(simpanSesiLokal(sesi, buntu)).toBe(false)
    expect(bacaSesiLokal(buntu)).toBeNull()
    expect(() => hapusSesiLokal(buntu)).not.toThrow()
  })
})

describe('pilihSesi', () => {
  const asli = { user: { id: 'u1', email: 'rian@tokokartini.app' } }
  const cache = { user: { id: 'u1', email: 'rian@tokokartini.app' }, lokal: true }

  it('sesi server menang -- itu satu-satunya yang punya token sah', () => {
    expect(pilihSesi(asli, cache)).toBe(asli)
  })

  it('token mati tanpa sinyal: jatuh ke sesi lokal, BUKAN halaman login', () => {
    expect(pilihSesi(null, cache)).toBe(cache)
  })

  it('belum pernah login di HP ini: halaman login', () => {
    expect(pilihSesi(null, null)).toBeNull()
  })

  it('sesudah tombol Keluar (identitas sudah dihapus): halaman login', () => {
    expect(pilihSesi(null, null)).toBeNull()
  })
})

describe('logoutSungguhan', () => {
  const jaringan = (e) => e?.tipe === 'jaringan'

  it('gagal karena sinyal: tetap di mode lokal', () => {
    expect(logoutSungguhan({ tipe: 'jaringan' }, jaringan)).toBe(false)
  })

  it('refresh token ditolak pusat: pulangkan ke login', () => {
    expect(logoutSungguhan({ tipe: 'auth' }, jaringan)).toBe(true)
  })

  it('tidak ada error sama sekali: bukan logout', () => {
    expect(logoutSungguhan(null, jaringan)).toBe(false)
  })
})

describe('sesi milik auth-js', () => {
  const URL_SB = 'https://qfqulgkpbjceizrapyom.supabase.co'
  const KUNCI = 'sb-qfqulgkpbjceizrapyom-auth-token'

  it('menebak nama slot persis seperti bawaan supabase-js', () => {
    expect(kunciSesiServer(URL_SB)).toBe(KUNCI)
  })

  it('URL rusak tidak melempar, cuma tidak ada yang dibuang', () => {
    expect(kunciSesiServer(undefined)).toBeNull()
    expect(kunciSesiServer('bukan url')).toBeNull()
    expect(lupakanSesiServer(undefined, storePalsu())).toBe(false)
  })

  it('membuang sesi server supaya Keluar offline tidak balik login sendiri', () => {
    const store = storePalsu({ [KUNCI]: '{"refresh_token":"x"}', [`${KUNCI}-code-verifier`]: 'v' })
    expect(lupakanSesiServer(URL_SB, store)).toBe(true)
    expect(store.getItem(KUNCI)).toBeNull()
    expect(store.getItem(`${KUNCI}-code-verifier`)).toBeNull()
  })

  it('tidak menyentuh antrian hitungan milik aplikasi', () => {
    const store = storePalsu({ [KUNCI]: 'x', 'so-outbox-v1': '[{"id":"lokal:1"}]' })
    lupakanSesiServer(URL_SB, store)
    expect(store.getItem('so-outbox-v1')).toBe('[{"id":"lokal:1"}]')
  })
})
