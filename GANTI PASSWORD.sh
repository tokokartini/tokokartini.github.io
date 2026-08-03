#!/bin/bash
# Pengganti "GANTI PASSWORD.bat" untuk Linux.
# Klik dua kali file ini, lalu pilih "Run in Terminal".
cd "$(dirname "$0")" || exit 1
bash scripts/ganti_password.sh
echo
read -r -p "Tekan Enter untuk menutup jendela ini. " _
