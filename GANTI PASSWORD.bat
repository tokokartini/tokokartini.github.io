@echo off
title Ganti Password SO Kartini
cd /d "%~dp0scripts"
echo.
echo  =================================
echo   GANTI PASSWORD AKUN SO KARTINI
echo  =================================
echo.
echo  Ketik nama akun lalu Enter. Contoh: admin
echo.
set /p AKUN="  Nama akun: "
echo.
python ganti_password.py %AKUN%
echo.
echo  Selesai. Tekan tombol apa saja untuk menutup.
pause >nul
