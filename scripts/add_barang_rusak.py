# -*- coding: utf-8 -*-
"""Pasang tab 'Barang Rusak' — kerugian barang yang keluar bukan karena terjual.

    python3 -u add_barang_rusak.py            # pasang / perbarui tab
    python3 -u add_barang_rusak.py --uji      # uji formula di tab sementara, lalu dihapus

Aman diulang. Cuma menulis judul + formula di tab Barang Rusak, tidak menyentuh
tab lain.

Sumbernya tab Mutasi baris berjenis `Rusak` (kolom L Sebab). Formula, bukan skrip
yang menulis angka, supaya ikut terbarui sendiri tiap ada surat jalan baru.

Yang ditampilkan bukan "12 pcs rusak" tapi "Rp 340 rb hangus" — nilainya dari tab
Harga lewat SKU. Tanpa rupiah, daftar ini cuma jadi catatan; dengan rupiah, jadi
alasan untuk berbuat sesuatu.

Locale sheet `in_ID`: pemisah argumen `;` dan pemisah kolom array `\\`.
"""
import argparse
import os
import socket
import sys
import time
import warnings

TAB = "Barang Rusak"
JUDUL = ["Tanggal", "Sebab", "Dari", "SKU", "Produk", "Satuan", "Qty", "Staff", "Nilai HPP"]

# Mutasi: A Waktu, B Staff, C Jenis, D Dari, E Ke, F Produk, G Rincian, H Qty,
# I Satuan, J SKU, K Nota, L Sebab.
# Col10 sengaja waktu PENUH walau yang ditampilkan cuma tanggalnya: mengurutkan
# pakai tanggal saja bikin baris di hari yang sama keluar dengan urutan acak.
SUMBER = (r"{ARRAYFORMULA(LEFT(Mutasi!A2:A;10))\Mutasi!L2:L\Mutasi!D2:D\Mutasi!J2:J"
          r"\Mutasi!F2:F\Mutasi!I2:I\Mutasi!H2:H\Mutasi!B2:B\Mutasi!C2:C\Mutasi!A2:A}")

RINCI = ('=IFERROR(QUERY(' + SUMBER +
         ';"select Col1, Col2, Col3, Col4, Col5, Col6, Col7, Col8 '
         'where Col9 = \'Rusak\' order by Col10 desc";0);"belum ada barang rusak tercatat")')

# Nilai dihitung di kolom bantu, BUKAN di dalam QUERY: QUERY tidak bisa memanggil
# VLOOKUP ke tab lain. Kolom ini membaca daerah tumpahan QUERY di sebelah kirinya.
NILAI = ('=ARRAYFORMULA(IF($D$2:$D="";"";'
         'IFERROR($G$2:$G*VLOOKUP($D$2:$D;Harga!$A:$E;5;FALSE);"")))')

# Ringkasan per sebab di kanan, supaya sekali lihat ketahuan mana yang paling mahal.
PER_SEBAB = ('=IFERROR(QUERY(' + SUMBER +
             ';"select Col2, count(Col5), sum(Col7) where Col9 = \'Rusak\' group by Col2 '
             'order by sum(Col7) desc '
             'label Col2 \'Sebab\', count(Col5) \'Baris\', sum(Col7) \'Total Qty\'";0);'
             '"belum ada data")')

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
    rinci = RINCI.replace(SUMBER, sumber)
    per_sebab = PER_SEBAB.replace(SUMBER, sumber)
    ws.update(values=[JUDUL], range_name="A1")
    ws.update(values=[[rinci]], range_name="A2", value_input_option="USER_ENTERED")
    ws.update(values=[[NILAI]], range_name="I2", value_input_option="USER_ENTERED")
    ws.update(values=[["PER SEBAB"], [per_sebab]], range_name="K1",
              value_input_option="USER_ENTERED")
    ws.format("A1:I1", {"textFormat": {"bold": True}})
    ws.format("K1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)


def uji_di_sheet(sh):
    """Mutasi palsu di tab sementara, formula dipasang di atasnya, hasilnya diperiksa."""
    palsu = buka(sh, "ZZ Uji Mutasi", 12, baris=50)
    palsu.clear()
    palsu.update(values=[
        ["Waktu", "Staff", "Jenis", "Dari", "Ke", "Produk", "Rincian", "Qty", "Satuan",
         "SKU", "Nota", "Sebab"],
        # Alu Cup 53/24 HPP 2930 -> 4 x 2930 = 11720
        ["2026-08-25 09:00:00", "rian", "Rusak", "Gudang Ciherang", "Barang Rusak",
         "Alu Cup 53/24", "", 4, "Pack (10pcs)", "ALC-0002-3", "", "Kadaluarsa"],
        # Alu Cup 212/57 HPP 8620 -> 2 x 8620 = 17240
        ["2026-08-25 10:00:00", "dewo", "Rusak", "Area Display", "Barang Rusak",
         "Alu Cup 212/57", "", 2, "Pack (10pcs)", "ALC-0001-3", "", "Rusak / pecah"],
        # Bukan jenis Rusak -> TIDAK boleh muncul sama sekali
        ["2026-08-25 11:00:00", "rian", "Isi Ulang", "Gudang Ciherang", "Area Display",
         "Alu Cup 53/24", "", 9, "Pack (10pcs)", "ALC-0002-3", "", ""],
    ], range_name="A1")

    uji = buka(sh, "ZZ Uji Rusak", 16, baris=50)
    uji.clear()
    pasang(uji, SUMBER.replace("Mutasi!", "'ZZ Uji Mutasi'!"))
    time.sleep(3)

    hasil = uji.get_all_values()
    baris = [r for r in hasil[1:] if r and r[0].strip()]
    print(f"   {len(baris)} baris keluar dari 3 baris Mutasi palsu", flush=True)
    for r in baris:
        print("   ", r[:9], flush=True)

    def angka(t):
        return (str(t).replace("Rp", "").replace(" ", "").replace(".", "").replace(",", "."))

    gagal = []
    if len(baris) != 2:
        gagal.append(f"harusnya 2 baris (yang bukan Rusak dibuang), dapat {len(baris)}")
    else:
        if baris[0][7] != "dewo":
            gagal.append(f"urutan salah, terbaru harus di atas: {baris[0]}")
        nilai = {r[4]: angka(r[8]) for r in baris}
        if nilai.get("Alu Cup 53/24") != "11720":
            gagal.append(f"Nilai HPP kadaluarsa salah: {nilai} (harusnya 11720)")
        if nilai.get("Alu Cup 212/57") != "17240":
            gagal.append(f"Nilai HPP rusak salah: {nilai} (harusnya 17240)")
        if not any(r[1] == "Kadaluarsa" for r in baris):
            gagal.append(f"kolom Sebab tidak terbaca: {baris}")
        if not any(r[2] == "Area Display" for r in baris):
            gagal.append("barang rusak dari display harus ikut tercatat")

    sebab = uji.get("K2:M5")
    print(f"   blok PER SEBAB: {sebab}", flush=True)
    if not any("Kadaluarsa" in str(r) for r in sebab):
        gagal.append("blok PER SEBAB tidak memuat Kadaluarsa")

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

    print("Uji formula di tab sementara (tab Mutasi asli tidak disentuh):", flush=True)
    if not uji_di_sheet(sh):
        print(f"\nFormula belum benar — tab {TAB} TIDAK dipasang.", flush=True)
        return 1
    if hanya_uji:
        return 0

    pasang(buka(sh, TAB, 16))
    print(f"\nTab '{TAB}' terpasang. Ikut terbarui sendiri tiap ada surat jalan baru.",
          flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uji", action="store_true", help="uji formula saja, jangan pasang tabnya")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    asli = socket.getaddrinfo
    socket.getaddrinfo = lambda h, p, f=0, t=0, pr=0, fl=0: asli(h, p, socket.AF_INET, t, pr, fl)
    return jalan(a.uji)


if __name__ == "__main__":
    sys.exit(main())
