# -*- coding: utf-8 -*-
"""Ganti password akun SO Kartini tanpa lewat Dashboard.

Pakai: python ganti_password.py <username>
Contoh: python ganti_password.py admin

Password diketik langsung di terminal dan tidak ditampilkan di layar.
Butuh: scripts/config.local.json {"supabase_url": ..., "service_role_key": ...}
"""
import getpass
import json
import sys
from pathlib import Path

import requests

CONFIG = json.loads((Path(__file__).parent / "config.local.json").read_text())
BASE = CONFIG["supabase_url"].rstrip("/")
KEY = CONFIG["service_role_key"]
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}


def main(username):
    email = f"{username.strip().lower()}@tokokartini.app"

    r = requests.get(f"{BASE}/auth/v1/admin/users?per_page=100", headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    users = data.get("users", data) if isinstance(data, dict) else data
    target = next((u for u in users if u["email"] == email), None)
    if not target:
        print(f"GAGAL: akun {email} tidak ditemukan.")
        print("Akun yang ada:", ", ".join(sorted(u["email"].split("@")[0] for u in users)))
        sys.exit(1)

    print(f"Ganti password untuk: {email}")
    baru = getpass.getpass("Password baru (tidak tampil saat diketik): ")
    if len(baru) < 8:
        print("GAGAL: password minimal 8 karakter.")
        sys.exit(1)
    if baru != getpass.getpass("Ketik ulang password baru: "):
        print("GAGAL: kedua password tidak sama.")
        sys.exit(1)

    r = requests.put(
        f"{BASE}/auth/v1/admin/users/{target['id']}",
        headers=HEADERS,
        json={"password": baru},
        timeout=30,
    )
    if r.status_code == 200:
        print(f"OK: password {email} sudah diganti. Coba login di app sekarang.")
    else:
        print(f"GAGAL ({r.status_code}): {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
