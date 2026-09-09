<#
  build.ps1 — dựng bộ Kiosk Windows.

  .\scripts\build.ps1                # build exe + gói update + version.json
  .\scripts\build.ps1 -Installer     # + build Setup.exe (cần Inno Setup / iscc)

  Kết quả trong dist/:
    dist\GoSoKiosk\                     (onedir: 3 exe + assets + VERSION)
    dist\GoSoKiosk_Update_<ver>.zip     (gói auto-update — chỉ binaries)
    dist\version.json                  ({version, sha256, mandatory})
    dist\GoSoKiosk_Setup_<ver>.exe      (nếu -Installer)

  KHÔNG đưa config.json / device.json / logs / database vào bất kỳ artifact nào.
#>
param([switch]$Installer)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = (Get-Content (Join-Path $Root "VERSION") -Raw).Trim()
if (-not $Version) { throw "Không đọc được VERSION" }
Write-Host "==> GoSo Kiosk build  v$Version" -ForegroundColor Cyan

# --- kiểm tra công cụ / phụ thuộc ---
python --version | Out-Null
foreach ($m in @("PyInstaller","customtkinter","PIL","requests","win32print")) {
  python -c "import $m" 2>$null
  if ($LASTEXITCODE -ne 0) { throw "Thiếu phụ thuộc Python: $m  (pip install -r kiosk/requirements.txt pyinstaller)" }
}

# --- version metadata cho .exe (Windows) ---
# đệm để "1", "1.0", "1.0.0" đều ra đủ 4 số filevers/prodvers
$p = @($Version -split '\.') + @('0','0','0','0')
$verInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($($p[0]), $($p[1]), $($p[2]), 0),
    prodvers=($($p[0]), $($p[1]), $($p[2]), 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'Van phong Dang ky Dat dai'),
        StringStruct('FileDescription', 'GoSo Kiosk'),
        StringStruct('FileVersion', '$Version'),
        StringStruct('InternalName', 'GoSoKiosk'),
        StringStruct('ProductName', 'GoSo Kiosk'),
        StringStruct('ProductVersion', '$Version')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
Set-Content -Path (Join-Path $Root "build_version_info.txt") -Value $verInfo -Encoding UTF8

# --- clean ---
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue

# --- PyInstaller ---
Write-Host "==> PyInstaller..." -ForegroundColor Cyan
pyinstaller GoSoKiosk.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build lỗi" }

$App = Join-Path $Root "dist\GoSoKiosk"
foreach ($e in @("GoSoKiosk.exe","GoSoConfig.exe","GoSoUpdater.exe")) {
  if (-not (Test-Path (Join-Path $App $e))) { throw "Thiếu $e trong dist\GoSoKiosk" }
}
Set-Content -Path (Join-Path $App "VERSION") -Value $Version -NoNewline -Encoding ascii

# --- gói auto-update (chỉ binaries ứng dụng) ---
$Zip = Join-Path $Root "dist\GoSoKiosk_Update_$Version.zip"
Write-Host "==> Đóng gói update -> $Zip" -ForegroundColor Cyan
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path (Join-Path $App "*") -DestinationPath $Zip -CompressionLevel Optimal

$Sha = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower()
$verJson = @{ version = $Version; sha256 = $Sha; mandatory = $false } | ConvertTo-Json
Set-Content -Path (Join-Path $Root "dist\version.json") -Value $verJson -Encoding UTF8
Write-Host "    sha256 = $Sha"

# --- Installer (tùy chọn) ---
if ($Installer) {
  $iscc = (Get-Command iscc -ErrorAction SilentlyContinue) `
        ?? (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue) `
        ?? "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  if ($iscc -is [string]) { if (-not (Test-Path $iscc)) { $iscc = $null } } else { $iscc = $iscc.Source }
  if (-not $iscc) {
    Write-Warning "Không tìm thấy Inno Setup (iscc). Bỏ qua bước tạo Setup.exe."
  } else {
    Write-Host "==> Inno Setup..." -ForegroundColor Cyan
    & $iscc "/DMyAppVersion=$Version" (Join-Path $Root "installer\GoSoKiosk.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup build lỗi" }
  }
}

Write-Host "==> XONG. Xem thư mục dist\" -ForegroundColor Green
Get-ChildItem dist | Select-Object Name, Length | Format-Table -AutoSize
