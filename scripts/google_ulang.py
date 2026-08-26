# -*- coding: utf-8 -*-
"""Coba ulang otomatis waktu Google Sheets membalas 5xx / 429.

Dipakai begini, sekali saja di awal skrip (sesudah IPv4 dipaksa):

    import google_ulang
    google_ulang.pasang()

Kenapa perlu: 2026-08-26 sheet **Master Pricelist** membalas
`APIError: [503]: The service is currently unavailable.` untuk 2 dari 3
percobaan, sementara sheet SO di detik yang sama sehat. Karena `harga_master.py`
adalah langkah PERTAMA jadwal malam, satu 503 mematikan seluruh hitungan malam
itu — dan tidak ada yang menonton halaman Actions jam 03.30. Sekali coba ulang
langsung lolos.

Yang TIDAK diulang, dan alasannya:

* Galat ber-status 4xx selain 429 — itu penolakan tetap (izin, id salah, kuota
  harian habis). Mengulanginya cuma memperlambat kegagalan yang sudah pasti.
* Permintaan yang MEMBUAT tab (`addSheet`) atau MENAMBAH baris (`append`).
  Keduanya tidak idempoten: kalau ternyata permintaan pertama mendarat lalu
  jawabannya yang hilang, ulangan bikin tab kembar atau baris dobel. Sisanya
  aman diulang karena skrip di sini selalu menulis ke RENTANG TETAP — menulis
  hal yang sama dua kali hasilnya sama.

Menulis ke tab Log sengaja tidak diurus di sini sama sekali: yang menulis Log
cuma Edge Function `upload-rak`, dan pernah ada 7 entri hilang permanen gara-gara
skrip menulis balik seluruh Log (2026-07-30).
"""
import random
import time

ULANGI_STATUS = {429, 500, 502, 503, 504}
JANGAN_ULANG = ("addSheet", "/values:append", ":append")

MAKS_COBA = 5
JEDA_AWAL = 1.5      # detik; berlipat dua tiap gagal: 1.5, 3, 6, 12
JEDA_MAKS = 20.0

_sudah_pasang = False


def _boleh_ulang(response, kwargs):
    if response is None or response.status_code not in ULANGI_STATUS:
        return False
    badan = str(kwargs.get("json") or kwargs.get("data") or "")
    return not any(p in badan for p in JANGAN_ULANG)


def bungkus(asli, maks_coba=MAKS_COBA, diam=False):
    """Kembalikan salinan `asli` yang mengulang sendiri waktu Google balas 5xx/429.

    Dipisah dari `pasang()` supaya bisa diuji tanpa jaringan dan tanpa gspread.
    """
    def request(self, method, endpoint, *args, **kwargs):
        jeda = JEDA_AWAL
        for coba in range(1, maks_coba + 1):
            try:
                return asli(self, method, endpoint, *args, **kwargs)
            except Exception as e:
                resp = getattr(e, "response", None)
                if coba == maks_coba or not _boleh_ulang(resp, kwargs):
                    raise
                # Jitter supaya beberapa skrip yang mulai bersamaan tidak
                # mengulang serempak dan menekan Google di detik yang sama.
                tidur = min(jeda, JEDA_MAKS) * (0.7 + 0.6 * random.random())
                if not diam:
                    print(f"   Google balas {resp.status_code}, ulang ke-{coba} "
                          f"sesudah {tidur:.1f} detik", flush=True)
                time.sleep(tidur)
                jeda *= 2

    return request


def pasang(maks_coba=MAKS_COBA, diam=False):
    """Bungkus `gspread.http_client.HTTPClient.request`. Aman dipanggil dua kali."""
    global _sudah_pasang
    if _sudah_pasang:
        return
    import gspread.http_client as hc

    hc.HTTPClient.request = bungkus(hc.HTTPClient.request, maks_coba, diam)
    _sudah_pasang = True


def uji():
    """Uji tanpa jaringan dan tanpa gspread: palsukan respons, hitung percobaan."""
    class Resp:
        def __init__(self, status_code):
            self.status_code = status_code

    class Galat(Exception):
        def __init__(self, response):
            self.response = response

    assert _boleh_ulang(Resp(503), {}), "503 harus diulang"
    assert _boleh_ulang(Resp(429), {}), "429 (kuota sesaat) harus diulang"
    assert not _boleh_ulang(Resp(404), {}), "404 penolakan tetap, jangan diulang"
    assert not _boleh_ulang(Resp(403), {}), "403 izin, jangan diulang"
    assert not _boleh_ulang(Resp(200), {}), "sukses jangan diulang"
    assert not _boleh_ulang(None, {}), "galat tanpa respons jangan diulang"
    assert not _boleh_ulang(Resp(503), {"json": {"requests": [{"addSheet": {}}]}}), \
        "bikin tab tidak idempoten, jangan diulang"
    assert not _boleh_ulang(Resp(503), {"json": {"x": "/values:append"}}), \
        "append tidak idempoten, jangan diulang"

    jeda_asli = time.sleep
    time.sleep = lambda d: None
    try:
        # Gagal dua kali lalu sukses -- persis kejadian 2026-08-26.
        n = {"v": 0}

        def dua_kali_gagal(self, method, endpoint, *a, **kw):
            n["v"] += 1
            if n["v"] < 3:
                raise Galat(Resp(503))
            return "OK"

        assert bungkus(dua_kali_gagal, diam=True)(None, "get", "x") == "OK"
        assert n["v"] == 3, f"harus dicoba 3 kali, malah {n['v']}"

        # 503 terus-terusan: menyerah sesudah MAKS_COBA, galatnya dilempar utuh.
        m = {"v": 0}

        def selalu_gagal(self, method, endpoint, *a, **kw):
            m["v"] += 1
            raise Galat(Resp(503))

        try:
            bungkus(selalu_gagal, maks_coba=4, diam=True)(None, "get", "x")
            raise AssertionError("harusnya melempar sesudah menyerah")
        except Galat:
            pass
        assert m["v"] == 4, f"harus berhenti di 4 percobaan, malah {m['v']}"

        # 403 langsung menyerah, tidak boleh diulang sama sekali.
        k = {"v": 0}

        def izin_ditolak(self, method, endpoint, *a, **kw):
            k["v"] += 1
            raise Galat(Resp(403))

        try:
            bungkus(izin_ditolak, diam=True)(None, "get", "x")
            raise AssertionError("403 harusnya dilempar")
        except Galat:
            pass
        assert k["v"] == 1, f"403 tidak boleh diulang, malah {k['v']} percobaan"
    finally:
        time.sleep = jeda_asli

    print("semua uji google_ulang LOLOS", flush=True)


if __name__ == "__main__":
    uji()
