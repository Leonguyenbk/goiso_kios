@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set GOISO_SECRET=f6ab3d792344b7164db0e22005640d3f002902aea6fc3d75ff13bb9260e85a1a
set GOISO_BASE_URL=https://goiso.kh2959bmt.xyz
if "%GOISO_PORT%"=="" set GOISO_PORT=5050
cd /d "%~dp0server"

echo ================================================
echo   MAY CHU HE THONG GOI SO - NHIEU CHI NHANH
echo ================================================
echo   Trang chu (chon chi nhanh) : http://localhost:%GOISO_PORT%/
echo   Man hinh   : http://localhost:%GOISO_PORT%/b/<ma-chi-nhanh>/display
echo   Ban goi so : http://localhost:%GOISO_PORT%/b/<ma-chi-nhanh>/counter
echo   Quan tri   : http://localhost:%GOISO_PORT%/admin
echo ------------------------------------------------

python -m pip install -q -r requirements.txt

if not exist "..\hethong_v2.db" (
  echo [!] Chua co CSDL - dang khoi tao va tao chi nhanh mau "eakar"...
  python manage.py init
)

REM Bat buoc dat GOISO_SECRET khi trien khai that (phia sau Cloudflare Tunnel).
if "%GOISO_SECRET%"=="" echo [!] Chua dat GOISO_SECRET - chi nen dung khi chay thu.

if "%GOISO_DEBUG%"=="1" (
  python app.py
) else (
  waitress-serve --listen=127.0.0.1:%GOISO_PORT% --threads=32 app:app
)
pause
