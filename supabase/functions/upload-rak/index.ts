import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function pemToDer(pem: string): Uint8Array {
  const b64 = pem.replace(/-----[^-]+-----/g, '').replace(/\\n/g, '').replace(/\s/g, '')
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
}

async function googleToken(email: string, key: string): Promise<string> {
  const now = Math.floor(Date.now() / 1000)
  const enc = (o: unknown) =>
    btoa(JSON.stringify(o)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  const unsigned = `${enc({ alg: 'RS256', typ: 'JWT' })}.${enc({
    iss: email,
    scope: 'https://www.googleapis.com/auth/spreadsheets',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  })}`
  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8', pemToDer(key), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign'],
  )
  const sig = new Uint8Array(
    await crypto.subtle.sign('RSASSA-PKCS1-v1_5', cryptoKey, new TextEncoder().encode(unsigned)),
  )
  const jwt = `${unsigned}.${btoa(String.fromCharCode(...sig)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')}`
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion=${jwt}`,
  })
  if (!r.ok) throw new Error(`google token: ${r.status}`)
  return (await r.json()).access_token
}

function wib(iso: string): string {
  const d = new Date(new Date(iso).getTime() + 7 * 3600 * 1000)
  return d.toISOString().slice(0, 19).replace('T', ' ')
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
    if (!user) return new Response('Unauthorized', { status: 401, headers: CORS })

    const { rack } = await req.json()
    if (!rack) return new Response('rack wajib', { status: 400, headers: CORS })

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)

    // Claim entries atomically: only rows this invocation flips from NULL -> now()
    // are ours to append. Any entry a concurrent invocation already claimed is
    // excluded, preventing doubled rows when two phones upload the same rack.
    const { data: entries, error: claimErr } = await admin
      .from('count_entries')
      .update({ uploaded_at: new Date().toISOString() })
      .eq('rack', rack)
      .eq('user_id', user.id)
      .is('uploaded_at', null)
      .select('*')
    if (claimErr) throw claimErr
    if (!entries.length) {
      return new Response(JSON.stringify({ uploaded: 0 }), {
        headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const ids = entries.map((e) => e.id)

    try {
      const rows: (string | number)[][] = []
      for (const e of entries) {
        const units = e.units as { sku: string; variant: string; mult: number; qty: number }[]
        const rows: (string | number)[][] = []

for (const e of entries) {
  const units = (e.units ?? []) as {
    sku: string
    variant: string
    mult: number
    qty: number
  }[]

  // Cari satuan terkecil (mult = 1).
  // Kalau tidak ada, ambil yang multiplier paling kecil.
  const baseUnit =
    units.find((u) => u.mult === 1) ??
    units.reduce(
      (smallest, current) =>
        current.mult < smallest.mult ? current : smallest,
      units[0]
    )

  if (!baseUnit) continue

  rows.push([
    wib(e.updated_at),
    e.username,
    e.rack,
    e.product_name,
    baseUnit.variant,
    baseUnit.sku,
    Number(e.qty_total ?? 0),
    e.expired_date ?? '',
  ])
}

      if (rows.length) {
        const token = await googleToken(Deno.env.get('GOOGLE_SA_EMAIL')!, Deno.env.get('GOOGLE_SA_KEY')!)
        const sheetId = Deno.env.get('SHEET_ID')!
        const r = await fetch(
          `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/Log!A1:append?valueInputOption=RAW&insertDataOption=OVERWRITE`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ values: rows }),
          },
        )
        if (!r.ok) throw new Error(`sheets append: ${r.status} ${await r.text()}`)
      }
    } catch (e) {
      // Rollback the claim so these entries aren't lost — a retry can pick them up.
      await admin.from('count_entries').update({ uploaded_at: null }).in('id', ids)
      throw e
    }

    return new Response(JSON.stringify({ uploaded: entries.length }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    console.error(e)
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
