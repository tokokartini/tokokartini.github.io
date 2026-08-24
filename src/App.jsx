import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Login from './pages/Login'
import Home from './pages/Home'
import Count from './pages/Count'
import Keluar from './pages/Keluar'
import Admin from './pages/Admin'
import { MODES } from './lib/mutasi'
import {
  bacaSesiLokal,
  hapusSesiLokal,
  logoutSungguhan,
  lupakanSesiServer,
  pilihSesi,
  simpanSesiLokal,
} from './lib/sesiLokal'
import { bacaOutbox, gagalJaringan } from './lib/outbox'

// Seberapa sering mencoba menghidupkan lagi sesi asli saat sedang jalan dari cache.
// Event `online` menangkap kebanyakan kasus; selang ini jaring pengaman untuk sinyal
// yang naik-turun tanpa pernah memicu event. Sengaja TIDAK 60 dtk: auth-js menyimpan
// kegagalan refresh selama 60 dtk dan menyajikannya lagi tanpa menyentuh jaringan,
// jadi selang yang selangkah dengan cooldown itu bisa terus kena jawaban basi.
const COBA_SAMBUNG_MS = 20000

// Berapa lama menunggu jawaban `getSession()` sebelum membuka aplikasi dari cache.
//
// Kalau token sudah kedaluwarsa, auth-js mencoba menyegarkannya dengan backoff
// bertingkat sampai ~30 detik sebelum menyerah. Tanpa sinyal, tiga puluh detik itu
// dihabiskan karyawan menatap layar "Memuat...". Jadi begitu identitasnya dikenal,
// aplikasi dibuka duluan dalam mode lokal; kalau ternyata sesinya masih sah, dia
// naik sendiri begitu jawabannya datang.
const BATAS_BOOT_MS = 1500

export default function App() {
  const [session, setSession] = useState(undefined)
  const [rack, setRack] = useState(null)
  // Halaman surat jalan yang sedang dibuka ('display' | 'datang' | 'gudang'), atau
  // null kalau petugas masih di menu. Sengaja terpisah dari `rack` supaya alur SO
  // tidak berubah sedikit pun.
  const [modeKey, setModeKey] = useState(null)

  useEffect(() => {
    let hidup = true
    const tersimpan = bacaSesiLokal()
    const jagaan = tersimpan
      ? setTimeout(() => {
        // Hanya kalau `getSession()` memang belum menjawab. Jawaban yang sudah
        // masuk -- termasuk "belum pernah login" -- tidak boleh ditimpa.
        if (hidup) setSession((lama) => (lama === undefined ? tersimpan : lama))
      }, BATAS_BOOT_MS)
      : null

    supabase.auth.getSession().then(({ data }) => {
      if (!hidup) return
      clearTimeout(jagaan)
      // Belum pernah login -> null -> halaman Login. Pernah login tapi token
      // kedaluwarsa tanpa sinyal -> sesi lokal, kerjanya jalan terus.
      if (data.session) simpanSesiLokal(data.session)
      setSession(pilihSesi(data.session, bacaSesiLokal()))
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => {
      // SIGNED_OUT punya dua arti yang sangat berbeda: karyawan menekan Keluar
      // (identitas sudah dihapus duluan oleh tombolnya, jadi ini balik ke null),
      // atau token mati tanpa sinyal -- yang itu BUKAN logout dan tidak boleh
      // menghentikan hitungan di tengah gudang.
      if (s) simpanSesiLokal(s)
      setSession(pilihSesi(s, bacaSesiLokal()))
    })
    return () => { hidup = false; clearTimeout(jagaan); sub.subscription.unsubscribe() }
  }, [])

  const tanpaSinyal = !!session?.lokal

  // Sedang jalan dari cache: terus coba pulihkan sesi asli. Berhasil -> onAuthStateChange
  // yang menaikkannya. Gagal karena bukan jaringan (akun dinonaktifkan admin, refresh
  // token dicabut) -> itu logout sungguhan, jangan digantung di mode offline selamanya.
  useEffect(() => {
    if (!tanpaSinyal) return
    let hidup = true
    const coba = async () => {
      const { data, error } = await supabase.auth.refreshSession()
      if (!hidup || data?.session) return
      if (logoutSungguhan(error, gagalJaringan)) {
        hapusSesiLokal()
        setSession(null)
      }
    }
    coba()
    window.addEventListener('online', coba)
    const timer = setInterval(coba, COBA_SAMBUNG_MS)
    return () => {
      hidup = false
      window.removeEventListener('online', coba)
      clearInterval(timer)
    }
  }, [tanpaSinyal])

  function keluar() {
    const antre = bacaOutbox().filter((it) => it.user_id === session?.user?.id).length
    if (antre && !window.confirm(
      `Masih ada ${antre} hitungan yang belum sampai ke pusat.\n\n` +
        'Hitungannya tetap tersimpan dan terkirim saat kamu login lagi, ' +
        'tapi lebih aman upload dulu. Tetap keluar?',
    )) return
    hapusSesiLokal()
    setSession(null)
    setRack(null)
    setModeKey(null)
    // `signOut()` mencabut sesi di sisi server DAN membuangnya dari HP -- tapi cuma
    // kalau sempat. Tanpa sinyal, dia lebih dulu tersangkut di percobaan penyegaran
    // token auth-js (backoff sampai ~30 detik) lalu menyerah TANPA membersihkan
    // slotnya, dan karyawan sudah lama menutup aplikasi. Akibatnya dia masuk lagi
    // sendiri begitu ponselnya dapat sinyal.
    const urlSb = import.meta.env.VITE_SUPABASE_URL
    if (navigator.onLine) {
      supabase.auth.signOut().catch(() => {}).finally(() => lupakanSesiServer(urlSb))
    } else {
      // Mencabut di server memang mustahil tanpa jaringan; yang penting sesinya
      // hilang dari HP ini sekarang juga, bukan setengah menit lagi.
      lupakanSesiServer(urlSb)
      supabase.auth.signOut().catch(() => {})
    }
  }

  if (session === undefined) return <p className="center">Memuat…</p>

  const username = session?.user?.email?.split('@')[0] || ''
  const isAdmin = username === 'admin'

  // Baris kedua app bar = konteks "aku siapa, lagi di mana". Tombol keluar pindah
  // ke sini supaya tidak diulang di tiap halaman.
  const subtitle = !session
    ? 'Toko Kartini'
    : isAdmin
      ? 'Dashboard admin'
      : modeKey
        ? `${username} · ${MODES[modeKey].judul}`
        : rack
          ? `${username} · ${rack}`
          : `Halo, ${username}! Semangat ya 🔥`

  return (
    <>
      <header className="appbar">
        <div className="appbar-in">
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">📦</span>
            <div style={{ minWidth: 0 }}>
              <div className="brand-title">Stok Opname</div>
              <div className="brand-sub">{subtitle}</div>
            </div>
          </div>
          {session && (
            <button className="icon-btn" aria-label="Keluar" title="Keluar" onClick={keluar}>
              ⏻
            </button>
          )}
        </div>
        {tanpaSinyal && (
          <div className="offline-bar" role="status">
            📴 Mode tanpa sinyal — hitungan tersimpan di HP, terkirim sendiri nanti.
          </div>
        )}
      </header>

      <main className={`page${session && !isAdmin && (rack || modeKey) ? ' has-actionbar' : ''}`}>
        {!session && <Login />}
        {session && isAdmin && (
          tanpaSinyal
            ? <ButuhSinyal judul="Dashboard admin butuh sinyal" />
            : <Admin username={username} />
        )}
        {session && !isAdmin && !rack && !modeKey && (
          <Home username={username} tanpaSinyal={tanpaSinyal} onStart={setRack} onKeluar={setModeKey} />
        )}
        {session && !isAdmin && modeKey && (
          // Surat jalan belum punya antrian offline -- tiap Simpan langsung menulis ke
          // DB. Kalau dibiarkan jalan tanpa sinyal, karyawan mengetik satu surat jalan
          // penuh lalu kehilangan semuanya. Lebih baik ditutup terang-terangan.
          tanpaSinyal
            ? <ButuhSinyal judul={`${MODES[modeKey].judul} butuh sinyal`} onKembali={() => setModeKey(null)} />
            : <Keluar session={session} modeKey={modeKey} onSelesai={() => setModeKey(null)} />
        )}
        {session && !isAdmin && rack && !modeKey && (
          <Count
            session={session}
            username={username}
            rack={rack}
            tanpaSinyal={tanpaSinyal}
            onChangeRack={() => setRack(null)}
          />
        )}
      </main>
    </>
  )
}

function ButuhSinyal({ judul, onKembali }) {
  return (
    <div className="card">
      <p className="section-title">{judul}</p>
      <p className="muted">
        Halaman ini menulis langsung ke pusat, jadi tidak bisa dipakai offline. Cari
        tempat bersinyal sebentar — aplikasi menyambung sendiri, tidak perlu login ulang.
      </p>
      {onKembali && (
        <button className="secondary" style={{ width: '100%' }} onClick={onKembali}>
          Kembali ke menu
        </button>
      )}
    </div>
  )
}
