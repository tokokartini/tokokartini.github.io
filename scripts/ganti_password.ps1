# Ganti password akun SO Kartini. Dijalankan lewat "GANTI PASSWORD.bat".
# Password diketik di jendela ini, dikirim lewat stdin ke curl, dan tidak pernah
# ditulis ke file mana pun maupun muncul di daftar proses.
$ErrorActionPreference = "Stop"
try {
  $cfgPath = Join-Path $PSScriptRoot "config.local.json"
  if (-not (Test-Path $cfgPath)) { throw "config.local.json tidak ada di $PSScriptRoot" }
  $cfg  = Get-Content $cfgPath -Raw | ConvertFrom-Json
  $base = $cfg.supabase_url.TrimEnd("/")
  $key  = $cfg.service_role_key

  Write-Host ""
  Write-Host "  =================================" -ForegroundColor Cyan
  Write-Host "   GANTI PASSWORD AKUN SO KARTINI" -ForegroundColor Cyan
  Write-Host "  =================================" -ForegroundColor Cyan
  Write-Host ""

  $raw = curl.exe -s "$base/auth/v1/admin/users?per_page=100" -H "apikey: $key" -H "Authorization: Bearer $key"
  $users = ($raw | ConvertFrom-Json).users
  if (-not $users) { throw "Tidak bisa mengambil daftar akun. Cek koneksi internet." }
  Write-Host ("  Akun: " + (($users | ForEach-Object { $_.email.Split("@")[0] } | Sort-Object) -join ", "))
  Write-Host ""

  $akun   = Read-Host "  Nama akun yang mau diganti"
  $email  = ($akun.Trim().ToLower()) + "@tokokartini.app"
  $target = $users | Where-Object { $_.email -eq $email }
  if (-not $target) { throw "Akun $email tidak ada." }

  Write-Host ""
  Write-Host "  Ketik password baru. Layar TIDAK bergerak saat mengetik - itu normal." -ForegroundColor Yellow
  $s1 = Read-Host "  Password baru" -AsSecureString
  $s2 = Read-Host "  Ketik ulang   " -AsSecureString
  function ToText($s) {
    $b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
    try { [Runtime.InteropServices.Marshal]::PtrToStringAuto($b) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b) }
  }
  $p1 = ToText $s1
  if ($p1.Length -lt 8)   { throw "Password minimal 8 karakter." }
  if ($p1 -ne (ToText $s2)) { throw "Kedua password tidak sama." }

  $body = @{ password = $p1 } | ConvertTo-Json -Compress
  $out = $body | curl.exe -s -w "`n%{http_code}" -X PUT "$base/auth/v1/admin/users/$($target.id)" -H "apikey: $key" -H "Authorization: Bearer $key" -H "Content-Type: application/json" -d "@-"
  $kode = ($out | Select-Object -Last 1)
  Write-Host ""
  if ($kode -eq "200") {
    Write-Host "  BERHASIL. Password $email sudah diganti." -ForegroundColor Green
    Write-Host "  Coba login sekarang di https://tokokartini.github.io" -ForegroundColor Green
  } else {
    Write-Host "  GAGAL (kode $kode). Jawaban server:" -ForegroundColor Red
    Write-Host ("  " + ($out | Select-Object -SkipLast 1))
  }
}
catch {
  Write-Host ""
  Write-Host "  GAGAL: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""
Write-Host "  Jendela ini sengaja dibiarkan terbuka. Tutup sendiri kalau sudah selesai."
