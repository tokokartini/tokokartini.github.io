import { createClient } from 'npm:@supabase/supabase-js@2'
import { buildMutasiRows } from './rows.ts'

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

    const { from, to } = await req.json()
    if (!from || !to) return new Response('from dan to wajib', { status: 400, headers: CORS })

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!)

    // Klaim atomik, pola yang sama dengan upload-rak: hanya baris yang benar-benar
    // dibalik NULL -> now() oleh pemanggilan ini yang jadi milik kita. Surat jalan
    // yang sudah diklaim pemanggilan lain otomatis tersisih, jadi dua HP menekan
    // Kirim bersamaan tidak menghasilkan baris dobel di sheet.
    const { data: moves, error: claimErr } = await admin
      .from('movements')
      .update({ uploaded_at: new Date().toISOString() })
      .eq('from_loc', from)
      .eq('to_loc', to)
      .eq('user_id', user.id)
      .is('uploaded_at', null)
      .select('*')
    if (claimErr) throw claimErr
    if (!moves.length) {
      return new Response(JSON.stringify({ uploaded: 0 }), {
        headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const ids = moves.map((m) => m.id)
    // Dilaporkan ke HP sebagai jumlah terkirim -- pakai jumlah baris yang benar-benar
    // masuk sheet, bukan jumlah baris yang diklaim, supaya barang tanpa satuan tidak
    // dihitung sebagai terkirim.
    let written = 0

    try {
      const { rows, skipped } = buildMutasiRows(moves)
      written = rows.length
      if (skipped.length) {
        console.warn(`barang tanpa satuan, dilewati: ${skipped.join(', ')}`)
      }

      if (rows.length) {
        const token = await googleToken(Deno.env.get('GOOGLE_SA_EMAIL')!, Deno.env.get('GOOGLE_SA_KEY')!)
        const sheetId = Deno.env.get('SHEET_ID')!
        // insertDataOption=OVERWRITE, bukan INSERT_ROWS: INSERT_ROWS menyisipkan baris
        // dan menggeser formula di tab lain. Pernah kejadian di tab Log.
        const r = await fetch(
          `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/Mutasi!A1:append?valueInputOption=RAW&insertDataOption=OVERWRITE`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ values: rows }),
          },
        )
        if (!r.ok) throw new Error(`sheets append: ${r.status} ${await r.text()}`)
      }
    } catch (e) {
      // Batalkan klaim supaya surat jalan tidak hilang -- percobaan ulang bisa
      // mengambilnya lagi.
      await admin.from('movements').update({ uploaded_at: null }).in('id', ids)
      throw e
    }

    return new Response(JSON.stringify({ uploaded: written }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    console.error(e)
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
