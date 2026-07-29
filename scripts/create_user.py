# -*- coding: utf-8 -*-
"""Buat akun karyawan SO Kartini (Supabase Auth admin API).

Pakai: python create_user.py <username> <password>
       python create_user.py --list

Username otomatis jadi email <username>@tokokartini.app (huruf kecil),
sama seperti pemetaan di halaman Login.
Butuh: scripts/config.local.json {"supabase_url": ..., "service_role_key": ...}
"""
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


def list_users():
    r = requests.get(f"{BASE}/auth/v1/admin/users?per_page=100", headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    users = data.get("users", data) if isinstance(data, dict) else data
    for u in users:
        print(f"- {u['email']}  (dibuat {u.get('created_at', '?')[:10]})")


def create_user(username, password):
    email = f"{username.strip().lower()}@tokokartini.app"
    r = requests.post(
        f"{BASE}/auth/v1/admin/users",
        headers=HEADERS,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=30,
    )
    if r.status_code in (200, 201):
        print(f"OK: akun {email} dibuat. Login di app pakai username '{username.strip().lower()}'.")
    else:
        print(f"GAGAL ({r.status_code}): {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        list_users()
    elif len(sys.argv) == 3:
        create_user(sys.argv[1], sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
