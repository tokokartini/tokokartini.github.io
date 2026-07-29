// Menjaga properti paling berisiko di desain ini: parseMaster.js (diuji Vitest)
// dan supabase/functions/sync-produk/index.ts (Edge Function, tidak bisa impor
// dari src/) memuat SALINAN PERSIS logika parser. Sampai sekarang cuma komentar
// "KEMBARAN" di kedua file yang menjaga itu -- tidak ada yang gagal kalau salah
// satu diubah tanpa yang lain. Test ini baca kedua file dari disk, ambil daerah
// parser (dari `const UNIT_SLOTS` sampai akhir `parseMaster`), buang anotasi
// TypeScript-only + kata `export`, ratakan whitespace, lalu bandingkan.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const JS_PATH = path.join(HERE, 'parseMaster.js')
const TS_PATH = path.join(HERE, '..', '..', 'supabase', 'functions', 'sync-produk', 'index.ts')

const MARKER_START = 'const UNIT_SLOTS'
const MARKER_END = 'return { products, skipped, dupes }'

function extractParserRegion(text, label) {
  const start = text.indexOf(MARKER_START)
  if (start === -1) throw new Error(`${label}: penanda awal "${MARKER_START}" tidak ditemukan`)
  const markerEnd = text.indexOf(MARKER_END, start)
  if (markerEnd === -1) throw new Error(`${label}: penanda akhir "${MARKER_END}" tidak ditemukan`)
  // `return { products, skipped, dupes }` sudah diakhiri `}` (penutup object literal
  // return), bukan `}` penutup fungsi -- cari `}` BERIKUTNYA, itu penutup parseMaster.
  const afterMarker = markerEnd + MARKER_END.length
  const closeBrace = text.indexOf('}', afterMarker)
  if (closeBrace === -1) throw new Error(`${label}: penutup fungsi parseMaster tidak ditemukan`)
  return text.slice(start, closeBrace + 1)
}

function stripExport(text) {
  return text.replace(/\bexport\s+/g, '')
}

// `new Set<string>()` -> `new Set()`
function stripGenericCall(text) {
  return text.replace(/\b(\w+)<[^<>]*>(?=\()/g, '$1')
}

// `.filter(Boolean) as number[]` -> `.filter(Boolean)`
function stripAsCast(text) {
  return text.replace(/\s+as\s+[\w[\]]+/g, '')
}

function findMatchingBrace(text, openIdx) {
  let depth = 0
  for (let i = openIdx; i < text.length; i++) {
    if (text[i] === '{') depth++
    else if (text[i] === '}') { depth--; if (depth === 0) return i }
  }
  throw new Error('kurung kurawal tidak seimbang')
}

// Pisah daftar parameter di tanda koma level-teratas (tidak masuk ke dalam
// ([{< ... >}]) supaya `Record<string, unknown>` dkk tidak ikut kepotong.
function splitTopLevel(s) {
  const parts = []
  let depth = 0
  let cur = ''
  for (const c of s) {
    if ('([{<'.includes(c)) depth++
    else if (')]}>'.includes(c)) depth--
    if (c === ',' && depth === 0) { parts.push(cur); cur = '' }
    else cur += c
  }
  if (cur.trim()) parts.push(cur)
  return parts
}

// Buang anotasi tipe parameter + return type dari `function NAME(params): RET {`.
// Hanya beroperasi di zona signature (sampai `{` badan fungsi) -- tidak pernah
// menyentuh `:` di dalam object literal badan fungsi (itu urusan JS asli, bukan
// anotasi TS), jadi aman dipakai di seluruh region sekaligus.
function stripSignatureTypes(text) {
  const re = /function\s+\w+\s*\(/g
  let out = ''
  let i = 0
  let m
  while ((m = re.exec(text))) {
    out += text.slice(i, m.index + m[0].length)
    let pos = m.index + m[0].length
    let depth = 1
    while (depth > 0) {
      if (text[pos] === '(') depth++
      else if (text[pos] === ')') depth--
      pos++
    }
    const paramsEnd = pos - 1
    const paramsRaw = text.slice(m.index + m[0].length, paramsEnd)
    const params = splitTopLevel(paramsRaw)
      .map((p) => p.replace(/:\s*[\s\S]*$/, '').trim())
      .filter(Boolean)
    out += params.join(', ') + ')'
    pos = paramsEnd + 1

    const rest = text.slice(pos)
    const ret = rest.match(/^\s*:\s*/)
    if (ret) {
      pos += ret[0].length
      if (text[pos] === '{') {
        pos = findMatchingBrace(text, pos) + 1
      } else {
        let d = 0
        while (true) {
          const c = text[pos]
          if (c === '(' || c === '[' || c === '<') d++
          else if (c === ')' || c === ']' || c === '>') d--
          else if (d === 0 && c === '{') break
          pos++
        }
      }
      // Tipe yang dibuang menelan spasi sebelum `{` badan fungsi juga (pos sekarang
      // persis di `{`) -- sisipkan satu spasi supaya "raw) {" tidak berubah jadi
      // "raw){" dan lolos beda dari sisi JS yang memang tidak punya return type.
      out += ' '
    }
    re.lastIndex = pos
    i = pos
  }
  out += text.slice(i)
  return out
}

// Buang anotasi tipe dari `const NAME: TYPE = ...` / `let NAME: TYPE = ...`
// (di luar maupun di dalam badan fungsi), termasuk yang tipenya sendiri
// mengandung `{ ... }` bersarang satu level (mis. `{ sku: string; ... }[]`).
function stripVarDeclTypes(text) {
  const re = /\b(const|let)\s+(\w+)\s*:\s*/g
  let out = ''
  let i = 0
  let m
  while ((m = re.exec(text))) {
    out += text.slice(i, m.index) + `${m[1]} ${m[2]} `
    let pos = m.index + m[0].length
    let depth = 0
    while (pos < text.length) {
      const c = text[pos]
      if ('([{<'.includes(c)) depth++
      else if (')]}>'.includes(c)) depth--
      else if (depth === 0 && c === '=') break
      pos++
    }
    i = pos
    re.lastIndex = pos
  }
  out += text.slice(i)
  return out
}

function normalizeWhitespace(text) {
  return text.replace(/\s+/g, ' ').trim()
}

function canonicalize(text, label) {
  let s = extractParserRegion(text, label)
  s = stripExport(s)
  s = stripSignatureTypes(s)
  s = stripVarDeclTypes(s)
  s = stripAsCast(s)
  s = stripGenericCall(s)
  return normalizeWhitespace(s)
}

describe('parseMaster kembaran (src/lib/parseMaster.js vs supabase/functions/sync-produk/index.ts)', () => {
  it('logika parser di kedua file identik setelah anotasi TS dibuang', () => {
    const jsSrc = readFileSync(JS_PATH, 'utf8')
    const tsSrc = readFileSync(TS_PATH, 'utf8')

    const jsCanon = canonicalize(jsSrc, 'parseMaster.js')
    const tsCanon = canonicalize(tsSrc, 'index.ts')

    // Sanity check ekstraksi berhasil ambil badan yang berarti, bukan string kosong
    // atau potongan kependekan (kalau ini gagal, kegagalannya di ekstraksi/regex
    // penanda, bukan di logika parser itu sendiri).
    expect(jsCanon.length).toBeGreaterThan(300)
    expect(tsCanon.length).toBeGreaterThan(300)

    expect(tsCanon).toBe(jsCanon)
  })
})
