# -*- coding: utf-8 -*-
"""Pasang tab 'Kadaluarsa' — barang mendekati ED, dari kolom H tab Log.

    python3 -u add_kadaluarsa.py            # pasang / perbarui tab Kadaluarsa
    python3 -u add_kadaluarsa.py --uji      # uji formula di tab sementara, lalu dihapus

Aman diulang. TIDAK menyentuh Log maupun tab lain — cuma menulis judul + formula
di tab Kadaluarsa.

Kenapa formula dan bukan skrip yang menulis angka: kolom ED sudah ada di Log dan
tidak butuh perbandingan waktu rumit seperti saldo, jadi QUERY biasa cukup. Dengan
formula, tabnya ikut terbarui sendiri tiap ada upload SO — tak ada yang perlu ingat
menjalankan apa pun.

Tanggal ED ditulis aplikasi dari `<input type="date">`, jadi bentuknya selalu
`YYYY-MM-DD`. Itu teks yang urutannya sama dengan urutan tanggalnya, jadi
`order by` langsung benar tanpa konversi.

Locale sheet `in_ID`: pemisah argumen `;` dan pemisah kolom array `\\`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Kadaluarsa"
JUDUL = ["ED", "SKU", "Produk", "Satuan", "Qty", "Rak", "Staff", "Waktu Hitung",
         "Sisa Hari", "Status", "Nilai HPP"]

# Sumber diambil dari Log: H ED, I SKU, D Produk, G Satuan, F Qty, C Rak, B Staff, A Waktu.
SUMBER = r"{Log!H2:H\Log!I2:I\Log!D2:D\Log!G2:G\Log!F2:F\Log!C2:C\Log!B2:B\Log!A2:A}"

# Kolom bantu ada di KANAN hasil QUERY supaya tidak bentrok dengan daerah tumpahannya.
F_SISA = '=ARRAYFORMULA(IF($A$2:$A="";"";IFERROR(DATEVALUE($A$2:$A)-TODAY();"ED tak terbaca")))'
F_STATUS = ('=ARRAYFORMULA(IF($A$2:$A="";"";'
            'IF(NOT(ISNUMBER($I$2:$I));"cek ED";'
            'IF($I$2:$I<0;"LEWAT";IF($I$2:$I<=30;"30 hari";IF($I$2:$I<=90;"90 hari";"aman"))))))')
# HPP dicari lewat SKU di tab Harga (A SKU ... E HPP). Produk tanpa harga dibiarkan kosong.
F_NILAI = ('=ARRAYFORMULA(IF($B$2:$B="";"";'
           'IFERROR($E$2:$E*VLOOKUP($B$2:$B;Harga!$A:$E;5;FALSE);"")))')


def formula_query(sumber=SUMBER):
    """QUERY yang mengambil semua baris Log yang kolom ED-nya terisi, terdekat dulu."""
    return ('=IFERROR(QUERY(' + sumber +
            ';"select Col1, Col2, Col3, Col4, Col5, Col6, Col7, Col8 '
            'where Col1 is not null and Col1 <> \'\' order by Col1";0);"")')


# --- Jaringan ---------------------------------------------------------------

# Bisa ditimpa lewat env SO_KEY_PATH supaya skrip yang sama bisa jalan di
# GitHub Actions, di mana kunci ditulis ke berkas sementara.
KEY_PATH = os.environ.get(
    "SO_KEY_PATH", "/home/pianqt/Documents/Claude AI/claude-code-powershel-1427d99324cd.json")
SHEET_ID = "1uP2ntR00nrstLXKTuCYw1IzWDKohQAKsaq3qeeApDgw"


def buka(sh, judul, kolom, baris=20000):
    import gspread
    try:
        ws = sh.worksheet(judul)
        if ws.col_count < kolom:
            ws.resize(rows=max(ws.row_count, baris), cols=kolom)
        return ws
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(judul, rows=baris, cols=kolom)


def pasang(ws, sumber=SUMBER):
    ws.update(values=[JUDUL], range_name="A1")
    ws.update(values=[[formula_query(sumber)]], range_name="A2",
              value_input_option="USER_ENTERED")
    ws.update(values=[[F_SISA, F_STATUS, F_NILAI]], range_name="I2",
              value_input_option="USER_ENTERED")
    ws.format("A1:K1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)


def uji_di_sheet(sh):
    """Tulis Log palsu di tab sementara, pasang formula di atasnya, periksa hasilnya."""
    import gspread
    hari_ini = time.strftime("%Y-%m-%d")
    tahun = int(hari_ini[:4])
    lewat = f"{tahun - 1}-01-15"        # sudah kadaluarsa
    dekat = f"{tahun + 5}-01-15"        # jauh di depan -> aman

    palsu = buka(sh, "ZZ Uji Log", 11, baris=50)
    palsu.clear()
    palsu.update(values=[
        ["Waktu", "Staff", "Rak", "Produk", "Rincian", "Qty", "Satuan", "ED", "SKU"],
        ["2026-08-25 09:00:00", "rian", "Area Display", "Alu Cup 212/57", "", 10,
         "Pack (10pcs)", dekat, "ALC-0001-3"],
        ["2026-08-25 09:01:00", "rian", "Gudang Ciherang", "Alu Cup 53/24", "", 4,
         "Pack (10pcs)", lewat, "ALC-0002-3"],
        # ED kosong -> tidak boleh muncul sama sekali
        ["2026-08-25 09:02:00", "rian", "Gudang Ciherang", "Tanpa ED", "", 7, "Pcs", "", "XXX"],
    ], range_name="A1")

    uji = buka(sh, "ZZ Uji Kadaluarsa", 12, baris=50)
    uji.clear()
    sumber = SUMBER.replace("Log!", "'ZZ Uji Log'!")
    pasang(uji, sumber)
    time.sleep(3)  # beri waktu sheet menghitung formula

    hasil = uji.get_all_values()
    baris = [r for r in hasil[1:] if r and r[0].strip()]
    print(f"   {len(baris)} baris keluar dari 3 baris Log palsu", flush=True)
    for r in baris:
        print("   ", r[:11], flush=True)

    gagal = []
    if len(baris) != 2:
        gagal.append(f"harusnya 2 baris (yang ED-nya kosong dibuang), dapat {len(baris)}")
    else:
        if baris[0][0] != lewat:
            gagal.append(f"urutan salah, ED terdekat harus di atas: {baris[0][0]} vs {lewat}")
        if baris[0][9] != "LEWAT":
            gagal.append(f"status ED lampau harus LEWAT, dapat {baris[0][9]!r}")
        if baris[1][9] != "aman":
            gagal.append(f"status ED jauh harus aman, dapat {baris[1][9]!r}")
        # Alu Cup 53/24 HPP 2930 x qty 4 = 11720
        if baris[0][10].replace(".", "").replace(",", "") not in ("11720", "1172000"):
            gagal.append(f"Nilai HPP salah: {baris[0][10]!r} (harusnya 11720)")
        if "-" not in baris[0][8]:
            gagal.append(f"Sisa Hari ED lampau harus minus: {baris[0][8]!r}")

    sh.del_worksheet(uji)
    sh.del_worksheet(palsu)
    print("   dua tab sementara dihapus", flush=True)
    if gagal:
        for g in gagal:
            print("   GAGAL:", g, flush=True)
        return False
    print("   semua pemeriksaan formula LOLOS", flush=True)
    return True


def jalan(hanya_uji):
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(SHEET_ID)

    print("Uji formula di tab sementara (Log asli tidak disentuh):", flush=True)
    if not uji_di_sheet(sh):
        print("\nFormula belum benar — tab Kadaluarsa TIDAK dipasang.", flush=True)
        return 1
    if hanya_uji:
        return 0

    pasang(buka(sh, TAB, 12))
    print(f"\nTab '{TAB}' terpasang. Ikut terbarui sendiri tiap ada upload SO.", flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true",
                    help="uji formula di tab sementara saja, jangan pasang tab Kadaluarsa")
    a = ap.parse_args()

    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
