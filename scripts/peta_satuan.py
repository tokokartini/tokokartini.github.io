# -*- coding: utf-8 -*-
"""Bangun / perbarui tab 'Peta Satuan Olsera'.

    python3 -u peta_satuan.py "<file Qty Produk Terjual.xlsx>"
    python3 -u peta_satuan.py --uji

Kenapa tab ini perlu ada. Export Olsera memakai kosakata satuan sendiri yang tidak
sama dengan master toko:

    Olsera: Botol SKLB 250ml | Carton (80pcs)
    Master: Botol SKLB 250ml | Bal (100 Pcs)

Nama produknya sama persis, isi kartonnya beda -- 80 lawan 100. Menebak otomatis
berarti stok display salah 20% tanpa tanda apa pun, dan angka stok yang salah
diam-diam lebih berbahaya daripada tidak ada angka. Jadi yang tidak yakin TIDAK
PERNAH ditebak; dia masuk tab ini untuk diisi manusia.

Yang perlu diisi Sopian cuma kolom **Isi**: berapa satuan dasar master dalam satu
satuan Olsera. `Carton (12 Pcs)` -> 12. Satu angka, bukan mengetik ulang nama varian.

Baris diurutkan dari omzet terbesar, jadi mengisi 50 baris teratas saja sudah
menutup ~80% omzet. Isi dari atas, berhenti kapan saja.

Dijalankan ulang dengan file export baru: baris yang sudah kamu isi TIDAK
tertimpa, produk baru ditambahkan di bawah.
"""
import argparse
import collections
import json
import re
import socket
import sys
import urllib.parse
import urllib.request
import warnings

TAB = "Peta Satuan Olsera"
JUDUL = ["Produk Olsera", "Varian Olsera", "Produk Master", "Satuan Dasar Master",
         "Isi", "Status", "Omzet"]

OTOMATIS = "otomatis"
SETARA = "otomatis (satuan disamakan)"
ISI_MANUAL = "isi kolom Isi"
TIDAK_ADA = "produk tidak ada di master"

# Master dan Olsera menyebut kemasan yang sama dengan kata berbeda. Ini murni beda
# kosakata, bukan tebakan isi: `Krtn (15 Kg)` dan `Carton (15 Kg)` kardus yang sama,
# dan angkanya sudah ada di master. Sebelum daftar ini ada, 81 baris (71% omzet)
# mendarat di kolom manual padahal jawabannya sudah tersimpan di master.
SINONIM_SATUAN = {
    "krtn": "carton", "ktn": "carton", "dus": "carton",
    "trs": "toros", "tros": "toros",
    "rol": "roll",
    "btl": "botol",
    "bks": "bungkus",
    "pc": "pcs", "piece": "pcs",
    "pak": "pack",
}


# --- Bagian murni ----------------------------------------------------------

def norm_nama(s):
    """Samakan gaya penulisan: `1*11,34Kg` dan `1 x 11.34 Kg` jadi satu bentuk."""
    s = str(s or "").lower().replace("×", "x").replace("*", "x").replace(",", ".")
    return re.sub(r"[^a-z0-9.]", "", s)


def norm_varian(s):
    # "1 Ons" dan "Ons" satuan yang sama; Olsera kadang menulis angka 1 di depan.
    return re.sub(r"^1(?=[a-z])", "", norm_nama(s))


def kata_satuan(u):
    """Kata satuan yang sudah disamakan kosakatanya. `Krtn` dan `Carton` -> 'carton'."""
    n = re.sub(r"[^a-z0-9]", "", str(u or "").lower())
    return SINONIM_SATUAN.get(n, n)


def pecah_satuan(v):
    """`Krtn (15 Kg)` -> ('carton', (15.0, 'kg')). Tanpa kurung -> (kata, None).

    Isi kurung tanpa angka (`Botol (700 ML)` tetap punya angka; `Pack (Besar)` tidak)
    dikembalikan sebagai (None, kata) supaya tidak pernah disamakan dengan angka.
    """
    v = str(v or "").strip()
    m = re.fullmatch(r"([^()]+)\(([^)]*)\)", v)
    if not m:
        return kata_satuan(v), None
    dalam = m.group(2).strip().lower()
    d = re.fullmatch(r"([\d.,]+)\s*(.*)", dalam)
    if d:
        return kata_satuan(m.group(1)), (float(d.group(1).replace(",", ".")), kata_satuan(d.group(2)))
    return kata_satuan(m.group(1)), (None, kata_satuan(dalam))


# Satuan takaran. Sengaja dipisah: `Pcs` boleh disamakan dengan `Kaleng` atau `Btl`
# (sama-sama "satu buah"), tapi TIDAK PERNAH dengan `Gr` atau `Ml` -- di situ jumlahnya
# jelas bukan 1 dan menebaknya berarti stok salah beberapa ratus kali lipat.
TAKARAN = {"gr", "gram", "kg", "ons", "ml", "l", "liter", "cc", "cl"}

# Kata Olsera untuk "satu buah". Master memakai kata khusus per produk (Kaleng, Btl,
# Pack, Box); Sopian menegaskan 2026-08-24 itu barang satuan yang sama.
SEBUTAN_SATUAN = {"pcs", "pc", "piece", "buah", "biji"}


def gram(u):
    """Berapa gram satu satuan, kalau satuannya memang berat tertulis. `250gr` -> 250."""
    n = re.sub(r"\s+", "", str(u or "").lower()).replace(",", ".")
    m = re.fullmatch(r"([\d.]*)(kg|gr|gram|g)", n)
    if not m:
        return None
    angka = float(m.group(1)) if m.group(1) else 1.0
    return angka * 1000 if m.group(2) == "kg" else angka


def cocok_setara(varian_olsera, senama):
    """Cari satuan master yang PASTI kemasan yang sama. -> (mult, alasan) | (None, None).

    Empat aturan, semuanya menuntut bukti tertulis -- tidak ada yang menebak isi:

      R1 kata satuan sama DAN isi kurungnya identik      Carton (12 Pcs) = Krtn (12 Pcs)
      R2 Olsera menulis polos, master punya TEPAT SATU
         satuan berkata itu                              Kg = Kg (1000 Gr)
      R3 dua-duanya polos, katanya sama                  Rol = Roll
      R4 kata satuan BEDA tapi isi kurung identik,
         dan cuma satu kandidat                          Bal (25Kg) = Zak (25 Kg)

    Yang sengaja TIDAK dicocokkan: isi kurung yang angkanya berbeda. `Carton (80pcs)`
    lawan `Bal (100 Pcs)` tetap masuk kolom manual -- itu justru kasus yang bikin tab
    ini dibuat.
    """
    ko, io = pecah_satuan(varian_olsera)
    sekata = [(p["variant"], float(p["mult"])) for p in senama if pecah_satuan(p["variant"])[0] == ko]

    for nama, mult in sekata:                                    # R1
        if io is not None and pecah_satuan(nama)[1] == io:
            return mult, nama
    if io is None and len(sekata) == 1:                          # R2
        return sekata[0][1], sekata[0][0]
    for nama, mult in sekata:                                    # R3
        if io is None and pecah_satuan(nama)[1] is None:
            return mult, nama
    if io is not None and io[0] is not None:                     # R4
        kandidat = [(p["variant"], float(p["mult"])) for p in senama
                    if pecah_satuan(p["variant"])[1] == io]
        if len(kandidat) == 1:
            return kandidat[0][1], kandidat[0][0]

    # R5 Olsera menuliskan ukurannya, master menyebut satuannya polos.
    #    `Botol (700 ML)` -> master `Botol`; `Toros (25 Pcs)` -> master `Trs`.
    #    Dikonfirmasi Sopian 2026-08-24: itu kemasan yang sama, Olsera cuma memperjelas
    #    ukurannya. Kandidat harus tunggal supaya master dengan dua `Pack` beda isi
    #    tetap ambigu dan jatuh ke kolom manual.
    if io is not None:
        polos = [(p["variant"], float(p["mult"])) for p in senama
                 if pecah_satuan(p["variant"])[0] == ko and pecah_satuan(p["variant"])[1] is None]
        if len(polos) == 1:
            return polos[0][1], polos[0][0]

    # R6 Olsera menulis `Pcs`, master memakai kata khusus untuk satu buahnya
    #    (`Kaleng`, `Btl`, `Pack`). Dikonfirmasi Sopian 2026-08-24.
    #    Satuan takaran dikecualikan: `Pcs` lawan `Gr` bukan 1.
    if io is None and ko in SEBUTAN_SATUAN and not sekata:
        dasar = satuan_dasar(senama)
        if dasar and kata_satuan(dasar["variant"]) not in TAKARAN and gram(dasar["variant"]) is None:
            return float(dasar["mult"]), dasar["variant"]

    # R7 dua-duanya berat tertulis -> pembagian biasa, bukan tebakan. `1Kg` / `250gr` = 4.
    go = gram(varian_olsera)
    if go:
        berat = [(p["variant"], gram(p["variant"])) for p in senama if gram(p["variant"])]
        dasar = satuan_dasar(senama)
        if dasar and gram(dasar["variant"]) and float(dasar["mult"]) == 1:
            return go / gram(dasar["variant"]), dasar["variant"]
        del berat
    return None, None


def indeks_master(produk):
    by_nv, by_name = {}, collections.defaultdict(list)
    for p in produk:
        by_nv.setdefault((norm_nama(p["product_name"]), norm_varian(p["variant"])), p)
        by_name[norm_nama(p["product_name"])].append(p)
    return by_nv, by_name


def satuan_dasar(daftar):
    """Satuan dengan mult 1; kalau tidak ada, mult terkecil. Sama seperti rows.ts."""
    if not daftar:
        return None
    return min(daftar, key=lambda p: (float(p["mult"]) != 1, float(p["mult"])))


def susun_peta(penjualan, produk, peta_lama=None):
    """Kembalikan (baris, ringkasan).

    penjualan : [{'product','variant','omzet'}]
    produk    : baris tabel products
    peta_lama : {(produk_olsera, varian_olsera): isi_yang_sudah_diisi_manusia}
    """
    peta_lama = peta_lama or {}
    by_nv, by_name = indeks_master(produk)

    baris = []
    ringkas = collections.Counter()
    for row in penjualan:
        po, vo = str(row["product"]).strip(), str(row["variant"]).strip()
        kunci = (po, vo)
        cocok = by_nv.get((norm_nama(po), norm_varian(vo)))
        senama = by_name.get(norm_nama(po))
        dasar = satuan_dasar(senama)

        if kunci in peta_lama and peta_lama[kunci] not in ("", None):
            # Isian manusia menang atas tebakan apa pun -- jangan pernah ditimpa.
            isi, status = peta_lama[kunci], "diisi manual"
        elif cocok:
            isi, status = _rapi(float(cocok["mult"])), OTOMATIS
        elif senama and cocok_setara(vo, senama)[0] is not None:
            mult, dari = cocok_setara(vo, senama)
            isi, status = _rapi(mult), f"{SETARA}: {dari}"
        elif senama:
            isi, status = "", ISI_MANUAL
        else:
            isi, status = "", TIDAK_ADA

        ringkas[status] += 1
        baris.append([
            po, vo,
            (senama[0]["product_name"] if senama else ""),
            (dasar["variant"] if dasar else ""),
            isi, status, _rapi(row.get("omzet", 0)),
        ])

    # Yang butuh tangan manusia naik ke atas, diurutkan omzet terbesar, supaya
    # mengisi dari baris pertama langsung menutup porsi omzet terbesar.
    baris.sort(key=lambda b: (b[5] in (OTOMATIS, "diisi manual") or b[5].startswith(SETARA),
                              -float(b[6] or 0)))
    return baris, ringkas


def _rapi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    return int(x) if x.is_integer() else round(x, 4)


# --- Uji --------------------------------------------------------------------

def uji():
    produk = [
        {"sku": "A-G", "product_name": "Botol SKLB 250ml", "variant": "Bal (100 Pcs)", "mult": 100},
        {"sku": "A-1", "product_name": "Botol SKLB 250ml", "variant": "Pcs", "mult": 1},
        {"sku": "B-1", "product_name": "Almond Slice Blue Diamond 1*11,34Kg", "variant": "Ons", "mult": 1},
    ]
    jual = [
        {"product": "Botol SKLB 250ml", "variant": "Carton (80pcs)", "omzet": 500},
        {"product": "Botol SKLB 250ml", "variant": "Pcs", "omzet": 100},
        {"product": "Almond Slice Blue Diamond 1 x 11.34 Kg", "variant": "1 Ons", "omzet": 300},
        {"product": "Barang Asing", "variant": "Pcs", "omzet": 50},
    ]
    baris, ringkas = susun_peta(jual, produk)
    per_kunci = {(b[0], b[1]): b for b in baris}

    karton = per_kunci[("Botol SKLB 250ml", "Carton (80pcs)")]
    assert karton[4] == "" and karton[5] == ISI_MANUAL, f"carton 80 vs bal 100 TIDAK boleh ditebak: {karton}"
    assert karton[3] == "Pcs", f"satuan dasar master salah: {karton}"

    pcs = per_kunci[("Botol SKLB 250ml", "Pcs")]
    assert pcs[4] == 1 and pcs[5] == OTOMATIS, f"varian yang sama persis harus otomatis: {pcs}"

    almond = per_kunci[("Almond Slice Blue Diamond 1 x 11.34 Kg", "1 Ons")]
    assert almond[4] == 1 and almond[5] == OTOMATIS, f"normalisasi 1*11,34Kg gagal: {almond}"

    asing = per_kunci[("Barang Asing", "Pcs")]
    assert asing[5] == TIDAK_ADA and asing[2] == "", f"produk asing salah label: {asing}"

    # Baris yang butuh tangan manusia harus di atas, omzet terbesar dulu.
    assert baris[0][5] in (ISI_MANUAL, TIDAK_ADA), f"urutan salah, yang perlu diisi harus di atas: {baris[0]}"
    assert float(baris[0][6]) >= float(baris[1][6]), "belum urut omzet"

    # Isian manusia tidak boleh tertimpa saat dijalankan ulang.
    lagi, _ = susun_peta(jual, produk, {("Botol SKLB 250ml", "Carton (80pcs)"): 80})
    ulang = {(b[0], b[1]): b for b in lagi}[("Botol SKLB 250ml", "Carton (80pcs)")]
    assert ulang[4] == 80 and ulang[5] == "diisi manual", f"isian manual tertimpa: {ulang}"

    # --- kosakata satuan: master sudah tahu jawabannya, cuma katanya beda ---
    produk2 = [
        {"sku": "C-1", "product_name": "Fresh Milk", "variant": "Pcs", "mult": 1},
        {"sku": "C-K", "product_name": "Fresh Milk", "variant": "Krtn (12 Pcs)", "mult": 12},
        {"sku": "D-1", "product_name": "Telur", "variant": "Gr", "mult": 1},
        {"sku": "D-K", "product_name": "Telur", "variant": "Kg (1000 Gr)", "mult": 1000},
        {"sku": "E-1", "product_name": "Cup Sealer", "variant": "Roll", "mult": 1},
        {"sku": "F-1", "product_name": "Creamer", "variant": "Kg", "mult": 1},
        {"sku": "F-Z", "product_name": "Creamer", "variant": "Zak (25 Kg)", "mult": 25},
        {"sku": "G-1", "product_name": "Thinwall", "variant": "Pcs", "mult": 1},
        {"sku": "G-A", "product_name": "Thinwall", "variant": "Krtn (12 Pcs)", "mult": 12},
        {"sku": "G-B", "product_name": "Thinwall", "variant": "Krtn (6 Pcs)", "mult": 6},
    ]
    jual2 = [
        {"product": "Fresh Milk", "variant": "Carton (12 Pcs)", "omzet": 900},   # R1
        {"product": "Telur", "variant": "Kg", "omzet": 800},                      # R2
        {"product": "Cup Sealer", "variant": "Rol", "omzet": 700},                # R3
        {"product": "Creamer", "variant": "Bal (25Kg)", "omzet": 600},            # R4
        {"product": "Thinwall", "variant": "Carton", "omzet": 500},               # ambigu
    ]
    b2 = {(b[0], b[1]): b for b in susun_peta(jual2, produk2)[0]}

    r1 = b2[("Fresh Milk", "Carton (12 Pcs)")]
    assert r1[4] == 12 and r1[5].startswith(SETARA), f"R1 Krtn=Carton gagal: {r1}"
    r2 = b2[("Telur", "Kg")]
    assert r2[4] == 1000 and r2[5].startswith(SETARA), f"R2 'Kg' polos ke 'Kg (1000 Gr)' gagal: {r2}"
    r3 = b2[("Cup Sealer", "Rol")]
    assert r3[4] == 1 and r3[5].startswith(SETARA), f"R3 Rol=Roll gagal: {r3}"
    r4 = b2[("Creamer", "Bal (25Kg)")]
    assert r4[4] == 25 and r4[5].startswith(SETARA), f"R4 Bal(25Kg)=Zak(25 Kg) gagal: {r4}"

    # Master punya DUA karton berbeda isi -> 'Carton' polos ambigu, jangan ditebak.
    amb = b2[("Thinwall", "Carton")]
    assert amb[4] == "" and amb[5] == ISI_MANUAL, f"karton ambigu TIDAK boleh ditebak: {amb}"

    # Jebakan lama harus tetap ditolak walau kosakata sudah disamakan.
    assert per_kunci[("Botol SKLB 250ml", "Carton (80pcs)")][5] == ISI_MANUAL

    # Isian manusia tetap menang atas jalur setara.
    tetap = {(b[0], b[1]): b for b in
             susun_peta(jual2, produk2, {("Fresh Milk", "Carton (12 Pcs)"): 99})[0]}
    assert tetap[("Fresh Milk", "Carton (12 Pcs)")][4] == 99, "isian manual tertimpa jalur setara"

    # --- R5/R6/R7: jawaban Sopian 2026-08-24 dijadikan aturan ---
    produk3 = [
        {"sku": "H-1", "product_name": "Monin Lemon", "variant": "Botol", "mult": 1},
        {"sku": "H-K", "product_name": "Monin Lemon", "variant": "Krtn (6 Botol)", "mult": 6},
        {"sku": "I-1", "product_name": "Thinwall 35", "variant": "Trs", "mult": 1},
        {"sku": "J-1", "product_name": "SKM Tiga Sapi", "variant": "Kaleng", "mult": 1},
        {"sku": "J-K", "product_name": "SKM Tiga Sapi", "variant": "Krtn (48 Kaleng)", "mult": 48},
        {"sku": "K-1", "product_name": "Wijen", "variant": "250gr", "mult": 1},
        {"sku": "L-1", "product_name": "Telur Curah", "variant": "Gr", "mult": 1},
        {"sku": "M-1", "product_name": "Kresek Dua", "variant": "Pack (50 Pcs)", "mult": 50},
        {"sku": "M-2", "product_name": "Kresek Dua", "variant": "Pack (100 Pcs)", "mult": 100},
        {"sku": "M-3", "product_name": "Kresek Dua", "variant": "Pcs", "mult": 1},
    ]
    jual3 = [
        {"product": "Monin Lemon", "variant": "Botol (700 ML)", "omzet": 900},   # R5
        {"product": "Thinwall 35", "variant": "Toros (50 Pcs)", "omzet": 800},   # R5 + sinonim
        {"product": "SKM Tiga Sapi", "variant": "Pcs", "omzet": 700},            # R6
        {"product": "Wijen", "variant": "1Kg", "omzet": 600},                    # R7
        {"product": "Telur Curah", "variant": "Pcs", "omzet": 500},              # R6 ditolak
        {"product": "Kresek Dua", "variant": "Pack (75 Pcs)", "omzet": 400},     # ambigu
    ]
    b3 = {(b[0], b[1]): b for b in susun_peta(jual3, produk3)[0]}

    r5 = b3[("Monin Lemon", "Botol (700 ML)")]
    assert r5[4] == 1 and r5[5].startswith(SETARA), f"R5 'Botol (700 ML)'->'Botol' gagal: {r5}"
    r5b = b3[("Thinwall 35", "Toros (50 Pcs)")]
    assert r5b[4] == 1 and r5b[5].startswith(SETARA), f"R5 'Toros (...)'->'Trs' gagal: {r5b}"
    r6 = b3[("SKM Tiga Sapi", "Pcs")]
    assert r6[4] == 1 and r6[5].startswith(SETARA), f"R6 'Pcs'->'Kaleng' gagal: {r6}"
    r7 = b3[("Wijen", "1Kg")]
    assert r7[4] == 4 and r7[5].startswith(SETARA), f"R7 1Kg/250gr harus 4: {r7}"

    # R6 TIDAK boleh menyamakan `Pcs` dengan satuan takaran -- di situ jelas bukan 1.
    tolak = b3[("Telur Curah", "Pcs")]
    assert tolak[4] == "" and tolak[5] == ISI_MANUAL, f"'Pcs' lawan 'Gr' TIDAK boleh jadi 1: {tolak}"

    # Master punya dua `Pack` beda isi -> ukuran yang tidak cocok tetap ambigu.
    amb2 = b3[("Kresek Dua", "Pack (75 Pcs)")]
    assert amb2[4] == "" and amb2[5] == ISI_MANUAL, f"pack ambigu TIDAK boleh ditebak: {amb2}"

    print("semua uji susun_peta LOLOS")


# --- Jaringan ---------------------------------------------------------------

KEY_PATH = "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json"
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def ambil_produk():
    cfg = json.load(open("/home/pianqt/Documents/Claude AI/so-kartini/scripts/config.local.json"))
    base, key = cfg["supabase_url"].rstrip("/"), cfg["service_role_key"]
    semua = []
    for off in range(0, 20000, 1000):
        url = f"{base}/rest/v1/products?" + urllib.parse.urlencode({
            "select": "sku,product_name,variant,mult", "active": "eq.true",
            "offset": str(off), "limit": "1000",
        })
        req = urllib.request.Request(url, headers={"apikey": key, "Authorization": "Bearer " + key})
        batch = json.load(urllib.request.urlopen(req, timeout=60))
        semua += batch
        if len(batch) < 1000:
            break
    return semua


def baca_export(path):
    import pandas as pd
    df = pd.read_excel(path)
    df = df[df["sales qty"].notna()]
    omzet = pd.to_numeric(df.get("subtotal sell price pos"), errors="coerce").fillna(0)
    return [{"product": p, "variant": v, "omzet": float(o)}
            for p, v, o in zip(df["product"], df["variant"], omzet)]


def jalan(path):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    jual = baca_export(path)
    produk = ambil_produk()
    print(f"export {len(jual)} baris, master {len(produk)} satuan produk", flush=True)

    # Pertahankan isian manusia dari jalannya yang lalu.
    peta_lama = {}
    try:
        lama = sh.worksheet(TAB).get_all_values()[1:]
        for r in lama:
            if len(r) >= 5 and r[4] not in ("", None) and len(r) >= 6 and r[5] == "diisi manual":
                peta_lama[(r[0].strip(), r[1].strip())] = r[4]
            elif len(r) >= 6 and r[4] not in ("", None) and r[5] == ISI_MANUAL:
                peta_lama[(r[0].strip(), r[1].strip())] = r[4]
        print(f"isian manual yang dipertahankan: {len(peta_lama)}", flush=True)
    except gspread.exceptions.WorksheetNotFound:
        pass

    baris, ringkas = susun_peta(jual, produk, peta_lama)

    try:
        ws = sh.worksheet(TAB)
        ws.clear()
        if ws.col_count < 7:
            ws.resize(rows=max(ws.row_count, 5000), cols=7)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(TAB, rows=5000, cols=7)

    ws.update(values=[JUDUL] + baris, range_name="A1")
    ws.format("A1:G1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)

    total = sum(float(b[6] or 0) for b in baris)
    perlu = [b for b in baris if b[5] in (ISI_MANUAL, TIDAK_ADA)]
    tertutup = total - sum(float(b[6] or 0) for b in perlu)
    print(f"\nTab '{TAB}' ditulis: {len(baris)} baris", flush=True)
    for status, n in ringkas.most_common():
        print(f"   {status:28} {n:4} baris", flush=True)
    print(f"\nomzet tercakup tanpa kerja manual: {tertutup/total*100:.1f}%", flush=True)

    kum = 0.0
    sisa = sum(float(b[6] or 0) for b in perlu)
    for n in (20, 50, 100, 150):
        kum = sum(float(b[6] or 0) for b in perlu[:n])
        print(f"   isi {n:3} baris teratas -> total tercakup {(tertutup+kum)/total*100:.1f}%", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("berkas", nargs="?", help="file Qty Produk Terjual dari Olsera (.xlsx)")
    ap.add_argument("--uji", action="store_true")
    a = ap.parse_args()

    if a.uji:
        uji()
        return 0
    if not a.berkas:
        ap.error("sebutkan file export Olsera, atau pakai --uji")

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)

    uji()  # pengaman: jangan menulis sheet dengan logika yang rusak
    jalan(a.berkas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
