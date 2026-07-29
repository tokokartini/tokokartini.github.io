import { createClient } from 'npm:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, 'Content-Type': 'application/json' } })

const ADMIN_EMAIL = 'admin@tokokartini.app'
const TAB = 'Master Pricelist New'

// pemToDer + googleToken disalin apa adanya dari supabase/functions/upload-rak/index.ts:8-38.
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

// Parsing Master Pricelist -> daftar produk.
// KEMBARAN: src/lib/parseMaster.js memuat fungsi murni yang sama, diuji dengan
// Vitest di src/lib/parseMaster.test.js (Edge Function ini tidak bisa
// mengimpor dari src/). Ubah keduanya bersamaan.

// (kolom SKU, kolom satuan, kolom isi) — isi null = grosir (isi 1)
const UNIT_SLOTS: [number, number, number | null][] = [[28, 6, null], [29, 8, 7], [30, 10, 9], [31, 12, 11]]

function parseIsi(raw: unknown): number | null {
  const s = String(raw ?? '').trim()
  if (!s || s === '-') return null
  const n = Number(s.replace(/\./g, '').replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

function parseMaster(rows: string[][]): { products: Record<string, unknown>[]; skipped: number; dupes: number } {
  const products: Record<string, unknown>[] = []
  const seen = new Set<string>()
  let skipped = 0
  let dupes = 0
  for (const raw of rows.slice(2)) {
    const row = [...raw]
    while (row.length < 32) row.push('')
    const name = String(row[3] ?? '').trim()
    if (!name || String(row[0] ?? '').trim().startsWith('===')) continue
    const units: { sku: string; satuan: string; isi: number | null; order: number }[] = []
    UNIT_SLOTS.forEach(([skuI, satI, isiI], order) => {
      const sku = String(row[skuI] ?? '').trim()
      if (!sku) return
      const satuan = String(row[satI] ?? '').trim()
      if (!satuan) { skipped++; return }
      const isi = isiI === null ? 1 : parseIsi(row[isiI])
      units.push({ sku, satuan, isi, order })
    })
    if (!units.length) continue
    const isis = units.map((u) => u.isi).filter(Boolean) as number[]
    const base = isis.length ? Math.max(...isis) : 1
    const broken = units.some((u) => u.isi === null)
    for (const u of units) {
      if (seen.has(u.sku)) { dupes++; continue }
      seen.add(u.sku)
      const mult = broken || !u.isi ? 1 : base / u.isi
      products.push({
        sku: u.sku,
        product_name: name,
        variant: u.satuan,
        mult: Math.round(mult * 10000) / 10000,
        unit_order: u.order,
        category: String(row[0] ?? '').trim(),
        brand: String(row[2] ?? '').trim(),
        active: true,
      })
    }
  }
  return { products, skipped, dupes }
}

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: CORS })

  const service = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  const admin = createClient(Deno.env.get('SUPABASE_URL')!, service)
  let source = ''

  try {
    // --- autentikasi dua jalur ---
    const auth = req.headers.get('Authorization') ?? ''
    const token = auth.replace(/^Bearer\s+/i, '')
    if (token && token === service) {
      source = 'jadwal'
    } else {
      const userClient = createClient(
        Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!,
        { global: { headers: { Authorization: auth } } },
      )
      const { data: { user } } = await userClient.auth.getUser()
      if (!user) return json({ ok: false, error: 'Unauthorized' }, 401)
      if (user.email !== ADMIN_EMAIL) return json({ ok: false, error: 'Forbidden' }, 403)
      source = 'manual'
    }

    // --- baca Master Pricelist ---
    const gToken = await googleToken(Deno.env.get('GOOGLE_SA_EMAIL')!, Deno.env.get('GOOGLE_SA_KEY')!)
    const sheetId = Deno.env.get('MASTER_SHEET_ID')!
    const r = await fetch(
      `https://sheets.googleapis.com/v4/spreadsheets/${sheetId}/values/${encodeURIComponent(TAB)}`,
      { headers: { Authorization: `Bearer ${gToken}` } },
    )
    if (!r.ok) throw new Error(`sheets read: ${r.status} ${await r.text()}`)
    const rows: string[][] = (await r.json()).values ?? []

    const { products, skipped } = parseMaster(rows)

    // --- SKU yang sudah ada, untuk hitung "baru" dan menentukan yang dinonaktifkan ---
    const existing: { sku: string; active: boolean }[] = []
    for (let page = 0; page < 20; page++) {
      const { data, error } = await admin.from('products')
        .select('sku, active').range(page * 1000, page * 1000 + 999)
      if (error) throw new Error(error.message)
      existing.push(...data)
      if (data.length < 1000) break
    }
    const adaSku = new Set(existing.map((p) => p.sku))
    const aktifSekarang = existing.filter((p) => p.active).length

    // --- pengaman: jangan pernah menonaktifkan massal karena pembacaan gagal ---
    if (aktifSekarang > 0 && products.length < aktifSekarang / 2) {
      const error = `Dibatalkan: sheet hanya menghasilkan ${products.length} produk, sedangkan sekarang ada ${aktifSekarang} produk aktif. Cek Master Pricelist.`
      await admin.from('sync_runs').insert({ source, ok: false, total: products.length, skipped, error })
      return json({ ok: false, error })
    }

    const added = products.filter((p) => !adaSku.has(p.sku as string)).length

    // --- upsert bertahap ---
    for (let i = 0; i < products.length; i += 500) {
      const { error } = await admin.from('products')
        .upsert(products.slice(i, i + 500), { onConflict: 'sku' })
      if (error) throw new Error(error.message)
    }

    // --- nonaktifkan SKU aktif yang hilang dari sheet ---
    const diSheet = new Set(products.map((p) => p.sku as string))
    const hilang = existing.filter((p) => p.active && !diSheet.has(p.sku)).map((p) => p.sku)
    for (let i = 0; i < hilang.length; i += 100) {
      const { error } = await admin.from('products')
        .update({ active: false }).in('sku', hilang.slice(i, i + 100))
      if (error) throw new Error(error.message)
    }

    await admin.from('sync_runs').insert({
      source, ok: true, total: products.length, added, deactivated: hilang.length, skipped,
    })
    return json({ ok: true, total: products.length, added, deactivated: hilang.length, skipped })
  } catch (e) {
    const pesan = String(e)
    if (source) await admin.from('sync_runs').insert({ source, ok: false, error: pesan })
    return json({ ok: false, error: pesan })
  }
})
