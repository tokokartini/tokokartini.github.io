# -*- coding: utf-8 -*-
"""Kelompokkan tanggal SO satu lokasi jadi SESI.

    python3 -u sesi_so.py       # jalankan uji, tanpa jaringan

Satu SO tidak selalu selesai dalam sehari. Gudang Packaging dihitung 29 Agu 2026
(186 baris) lalu diteruskan 30 Agu (140 baris) -- satu pekerjaan, dua tanggal.
Semua skrip di sini dulu menganggap "satu SO = satu tanggal", jadi hari pertama
dibuang: tab Stok cuma memuat 140 dari 326 baris Packaging, Bahan Kue 3 dari 45,
Dapur Cherry 3 dari 49. Tab Selisih SO lebih parah -- hari kedua dibandingkan
dengan hari pertama seolah dua SO berbeda, jadi tiap barang yang belum sempat
dihitung kemarin muncul sebagai "barang lebih".

Aturannya: hari yang BERSAMBUNG masuk sesi yang sama. Jeda dua hari atau lebih
memulai sesi baru. SO bulanan berikutnya otomatis jadi sesi baru dan
menggantikan yang lama, persis seperti perilaku dulu.
"""
from datetime import date, timedelta

# Jeda maksimal antar hari yang masih dianggap satu SO. 1 = hari bersambung.
JEDA_HARI = 1


def _tanggal(t):
    try:
        return date.fromisoformat(str(t)[:10])
    except ValueError:
        return None


def kelompok(tanggal):
    """Kembalikan daftar sesi, tiap sesi daftar tanggal 'YYYY-MM-DD' urut naik."""
    urut = sorted({str(t)[:10] for t in tanggal if _tanggal(t)})
    sesi = []
    for t in urut:
        if sesi and _tanggal(t) - _tanggal(sesi[-1][-1]) <= timedelta(days=JEDA_HARI):
            sesi[-1].append(t)
        else:
            sesi.append([t])
    return sesi


def terakhir(tanggal):
    """Kembalikan himpunan tanggal sesi SO paling akhir. Kosong kalau tak ada."""
    sesi = kelompok(tanggal)
    return set(sesi[-1]) if sesi else set()


def uji():
    assert kelompok([]) == []
    assert kelompok(["2026-08-29", "2026-08-30"]) == [["2026-08-29", "2026-08-30"]], \
        "hari bersambung harus satu sesi"
    assert kelompok(["2026-08-29 19:54:14", "2026-08-30 09:00:00"]) == \
        [["2026-08-29", "2026-08-30"]], "timestamp penuh harus dipotong ke tanggal"
    assert kelompok(["2026-08-01", "2026-08-10"]) == [["2026-08-01"], ["2026-08-10"]], \
        "jeda 9 hari harus jadi dua sesi"
    assert kelompok(["2026-08-29", "2026-08-31"]) == [["2026-08-29"], ["2026-08-31"]], \
        "jeda sehari kosong (2 hari) harus memutus sesi"
    assert kelompok(["2026-08-29", "2026-08-30", "2026-08-31"]) == \
        [["2026-08-29", "2026-08-30", "2026-08-31"]], "rantai tiga hari harus satu sesi"
    # Lintas bulan tetap bersambung -- 31 Agu ke 1 Sep itu sehari.
    assert kelompok(["2026-08-31", "2026-09-01"]) == [["2026-08-31", "2026-09-01"]]
    # Tanggal kembar tidak menggandakan apa pun.
    assert kelompok(["2026-08-29", "2026-08-29"]) == [["2026-08-29"]]
    assert terakhir(["2026-08-01", "2026-08-10", "2026-08-11"]) == {"2026-08-10", "2026-08-11"}
    assert terakhir([]) == set()
    assert terakhir(["bukan tanggal"]) == set(), "teks sampah tidak boleh bikin sesi"
    print("semua uji sesi_so LOLOS")


if __name__ == "__main__":
    uji()
