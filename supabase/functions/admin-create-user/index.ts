import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json' },
  })

const ADMIN_EMAIL = 'admin@tokokartini.app'
const BAN_SELAMANYA = '876000h' // ~100 tahun

// banned_until ada di respons GoTrue tapi belum ada di tipe User supabase-js.
const nonaktif = (u: unknown) => {
  const until = (u as { banned_until?: string }).banned_until
  return !!until && new Date(until) > new Date()
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })
  try {
    const auth = req.headers.get('Authorization') ?? ''
    const userClient = createClient(
      Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: auth } } },
    )
    const { data: { user } } = await userClient.auth.getUser()
    if (!user) return json({ ok: false, error: 'Unauthorized' }, 401)
    if (user.email !== ADMIN_EMAIL) return json({ ok: false, error: 'Forbidden' }, 403)

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
    const { action, username, password } = await req.json()

    const semuaUser = async () => {
      const { data, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 100 })
      if (error) throw new Error(error.message)
      return data.users
    }

    if (action === 'list') {
      const users = (await semuaUser())
        .map((u) => ({ email: u.email ?? '', created_at: u.created_at, banned: nonaktif(u) }))
        .sort((a, b) => a.email.localeCompare(b.email))
      return json({ ok: true, users })
    }

    if (action === 'create') {
      const uname = String(username ?? '').trim().toLowerCase()
      if (!/^[a-z0-9._-]{2,30}$/.test(uname))
        return json({ ok: false, error: 'Username 2-30 karakter: huruf kecil, angka, titik, strip' })
      const pass = String(password ?? '')
      if (pass.length < 8)
        return json({ ok: false, error: 'Password minimal 8 karakter' })
      const email = `${uname}@tokokartini.app`
      const { error } = await admin.auth.admin.createUser({ email, password: pass, email_confirm: true })
      if (error) {
        const dup = /already|registered|exists/i.test(error.message)
        return json({ ok: false, error: dup ? 'Username sudah dipakai' : error.message })
      }
      return json({ ok: true, username: uname })
    }

    if (action === 'deactivate' || action === 'reactivate') {
      const uname = String(username ?? '').trim().toLowerCase()
      const email = `${uname}@tokokartini.app`
      if (email === ADMIN_EMAIL)
        return json({ ok: false, error: 'Akun admin tidak bisa dihapus atau dinonaktifkan' })
      const target = (await semuaUser()).find((u) => u.email === email)
      if (!target) return json({ ok: false, error: 'Akun tidak ditemukan' })

      if (action === 'reactivate') {
        const { error } = await admin.auth.admin.updateUserById(target.id, { ban_duration: 'none' })
        if (error) return json({ ok: false, error: error.message })
        return json({ ok: true, mode: 'active', username: uname })
      }

      // Entri SO adalah catatan yang harus tetap ada: akun yang sudah pernah
      // input dinonaktifkan, bukan dihapus.
      const { count, error: hitungErr } = await admin
        .from('count_entries')
        .select('id', { count: 'exact', head: true })
        .eq('user_id', target.id)
      if (hitungErr) return json({ ok: false, error: hitungErr.message })

      if (!count) {
        const { error } = await admin.auth.admin.deleteUser(target.id)
        if (error) return json({ ok: false, error: error.message })
        return json({ ok: true, mode: 'deleted', username: uname, entries: 0 })
      }
      const { error } = await admin.auth.admin.updateUserById(target.id, { ban_duration: BAN_SELAMANYA })
      if (error) return json({ ok: false, error: error.message })
      return json({ ok: true, mode: 'banned', username: uname, entries: count })
    }

    return json({ ok: false, error: 'Action tidak dikenal' })
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500)
  }
})
