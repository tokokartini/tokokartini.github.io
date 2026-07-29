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
    if (user.email !== 'admin@tokokartini.app') return json({ ok: false, error: 'Forbidden' }, 403)

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)
    const { action, username, password } = await req.json()

    if (action === 'list') {
      const { data, error } = await admin.auth.admin.listUsers({ page: 1, perPage: 100 })
      if (error) return json({ ok: false, error: error.message })
      const users = data.users
        .map((u) => ({ email: u.email ?? '', created_at: u.created_at }))
        .sort((a, b) => a.email.localeCompare(b.email))
      return json({ ok: true, users })
    }

    if (action === 'create') {
      const uname = String(username ?? '').trim().toLowerCase()
      if (!/^[a-z0-9._-]{2,30}$/.test(uname))
        return json({ ok: false, error: 'Username 2-30 karakter: huruf kecil, angka, titik, strip' })
      if (String(password ?? '').length < 8)
        return json({ ok: false, error: 'Password minimal 8 karakter' })
      const email = `${uname}@tokokartini.app`
      const { error } = await admin.auth.admin.createUser({ email, password, email_confirm: true })
      if (error) {
        const dup = /already|registered|exists/i.test(error.message)
        return json({ ok: false, error: dup ? 'Username sudah dipakai' : error.message })
      }
      return json({ ok: true, username: uname })
    }

    return json({ ok: false, error: 'Action tidak dikenal' })
  } catch (e) {
    return json({ ok: false, error: String(e) }, 500)
  }
})
