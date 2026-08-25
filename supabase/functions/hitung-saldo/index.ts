import { createClient } from 'npm:@supabase/supabase-js@2'

// Fungsi ini TIDAK menghitung apa pun sendiri. Tugasnya cuma memicu workflow
// `Hitung saldo` di repo privat tokokartini/so-kartini-jadwal, yang menjalankan
// skrip Python asli dari repo aplikasi.
//
// Sengaja begitu: kalau logika hitung saldo diterjemahkan ke TypeScript di sini,
// akan ada EMPAT pasang berkas kembar (hitung_saldo, saldo_display, harga_lookup,
// arsip_saldo) yang harus diubah bersamaan selamanya. Repo ini sudah punya satu
// pasang kembar (parseMaster) dan butuh test khusus cuma untuk menjaganya. Dengan
// cara ini Python tetap satu-satunya sumber kebenaran angka stok.
//
// Konsekuensi yang harus jujur disampaikan ke pemakai: hasilnya TIDAK seketika.
// GitHub butuh sekitar satu menit, jadi tombolnya cuma bisa bilang "diminta",
// bukan "selesai".

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })

const ADMIN_EMAIL = 'admin@tokokartini.app'
const REPO = 'tokokartini/so-kartini-jadwal'

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })

  try {
    // Autentikasi dua jalur, sama seperti sync-produk: service key untuk
    // pemanggilan dari jadwal, sesi admin untuk tombol di halaman admin.
    const service = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    const auth = req.headers.get('Authorization') ?? ''
    const token = auth.replace(/^Bearer\s+/i, '')
    if (!token || token !== service) {
      const userClient = createClient(
        Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!,
        { global: { headers: { Authorization: auth } } },
      )
      const { data: { user } } = await userClient.auth.getUser()
      if (!user) return json({ ok: false, error: 'Unauthorized' }, 401)
      if (user.email !== ADMIN_EMAIL) return json({ ok: false, error: 'Forbidden' }, 403)
    }

    const gh = Deno.env.get('GITHUB_TOKEN')
    if (!gh) {
      return json({
        ok: false,
        error: 'GITHUB_TOKEN belum dipasang di secrets Supabase — hitung saldo masih '
          + 'bisa dijalankan dari halaman Actions repo so-kartini-jadwal.',
      }, 503)
    }

    const r = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${gh}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        // GitHub menolak permintaan tanpa User-Agent.
        'User-Agent': 'so-kartini',
      },
      body: JSON.stringify({ event_type: 'hitung-saldo' }),
    })
    // repository_dispatch yang berhasil membalas 204 tanpa isi.
    if (r.status !== 204) {
      const teks = (await r.text()).slice(0, 200)
      return json({ ok: false, error: `GitHub menolak (${r.status}): ${teks}` }, 502)
    }

    return json({
      ok: true,
      pesan: 'Perhitungan diminta. Angkanya muncul di sheet sekitar satu menit lagi.',
    })
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500)
  }
})
