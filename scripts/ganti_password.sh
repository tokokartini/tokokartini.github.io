#!/bin/bash
# Ganti password akun SO Kartini. Port Linux dari ganti_password.ps1 (Windows).
# Dijalankan lewat "GANTI PASSWORD.sh" di folder induk, atau langsung:
#   bash scripts/ganti_password.sh
#
# Password diketik tanpa ditampilkan, dikirim ke curl lewat stdin, dan tidak
# pernah ditulis ke file maupun muncul di argumen proses (ps).
# service_role_key juga tidak masuk argumen proses: dikirim lewat file config
# curl bermode 600 di /run/user (tmpfs, tidak menyentuh disk).
set -uo pipefail

SD="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$SD/config.local.json"

merah()  { printf '\033[0;31m%s\033[0m\n' "$*"; }
hijau()  { printf '\033[0;32m%s\033[0m\n' "$*"; }
kuning() { printf '\033[0;33m%s\033[0m\n' "$*"; }

gagal() { echo; merah "  GAGAL: $*"; echo; exit 1; }

[ -f "$CFG" ] || gagal "config.local.json tidak ada di $SD"

BASE=$(python3 -c "import json;print(json.load(open('$CFG'))['supabase_url'].rstrip('/'))") \
  || gagal "tidak bisa membaca supabase_url dari config.local.json"
KEY=$(python3 -c "import json;print(json.load(open('$CFG'))['service_role_key'])") \
  || gagal "tidak bisa membaca service_role_key dari config.local.json"

# file config curl: menyimpan header rahasia supaya tidak tampak di 'ps'
RUNDIR="${XDG_RUNTIME_DIR:-/tmp}"
HDR=$(mktemp "$RUNDIR/.sokartini-hdr.XXXXXX") || gagal "tidak bisa bikin file sementara"
chmod 600 "$HDR"
trap 'rm -f "$HDR"' EXIT INT TERM
{
  printf 'header = "apikey: %s"\n' "$KEY"
  printf 'header = "Authorization: Bearer %s"\n' "$KEY"
} > "$HDR"

echo
kuning "  ================================="
kuning "   GANTI PASSWORD AKUN SO KARTINI"
kuning "  ================================="
echo

RAW=$(curl -s -K "$HDR" "$BASE/auth/v1/admin/users?per_page=100") \
  || gagal "tidak bisa menghubungi server. Cek koneksi internet."

DAFTAR=$(printf '%s' "$RAW" | python3 -c "
import json,sys
try: u=json.load(sys.stdin).get('users') or []
except Exception: u=[]
print(', '.join(sorted(x['email'].split('@')[0] for x in u)))
")
[ -n "$DAFTAR" ] || gagal "Tidak bisa mengambil daftar akun. Cek koneksi internet."
echo "  Akun: $DAFTAR"
echo

read -r -p "  Nama akun yang mau diganti: " AKUN
AKUN=$(printf '%s' "$AKUN" | tr '[:upper:]' '[:lower:]' | xargs)
EMAIL="${AKUN}@tokokartini.app"

UID_TARGET=$(printf '%s' "$RAW" | python3 -c "
import json,sys
u=json.load(sys.stdin).get('users') or []
print(next((x['id'] for x in u if x['email']=='$EMAIL'), ''))
")
[ -n "$UID_TARGET" ] || gagal "Akun $EMAIL tidak ada."

echo
kuning "  Ketik password baru. Layar TIDAK bergerak saat mengetik - itu normal."
read -r -s -p "  Password baru: " P1; echo
read -r -s -p "  Ketik ulang  : " P2; echo

[ ${#P1} -ge 8 ]   || gagal "Password minimal 8 karakter."
[ "$P1" = "$P2" ]  || gagal "Kedua password tidak sama."

# body lewat stdin (-d @-), bukan argumen -> tidak tampak di 'ps'
OUT=$(python3 -c "
import json,sys
sys.stdout.write(json.dumps({'password': sys.stdin.readline().rstrip('\n')}))
" <<< "$P1" | curl -s -w '\n%{http_code}' -X PUT \
      -K "$HDR" -H "Content-Type: application/json" \
      "$BASE/auth/v1/admin/users/$UID_TARGET" -d @-)
unset P1 P2

KODE=$(printf '%s' "$OUT" | tail -1)
echo
if [ "$KODE" = "200" ]; then
  hijau "  BERHASIL. Password $EMAIL sudah diganti."
  hijau "  Coba login sekarang di https://tokokartini.github.io"
else
  merah "  GAGAL (kode $KODE). Jawaban server:"
  echo "  $(printf '%s' "$OUT" | head -n -1)"
fi
echo
