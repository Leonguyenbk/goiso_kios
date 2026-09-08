@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0server"

echo ================================================
echo   MAY CHU HE THONG GOI SO - NHIEU CHI NHANH
echo ================================================
echo   Trang chu (chon chi nhanh) : http://localhost:5000/
echo   Man hinh   : http://localhost:5000/b/<ma-chi-nhanh>/display
echo   Ban goi so : http://localhost:5000/b/<ma-chi-nhanh>/counter
echo   Quan tri   : http://localhost:5000/admin
echo ------------------------------------------------

python -m pip install -q -r requirements.txt

if not exist "..\hethong_v2.db" (
  echo [!] Chua co CSDL - dang khoi tao va tao chi nhanh mau "eakar"...
  python manage.py init
)

REM Bat buoc dat GOISO_SECRET khi trien khai that (phia sau Cloudflare Tunnel).
if "%GOISO_SECRET%"=="" echo [!] Chua dat GOISO_SECRET - chi nen dung khi chay thu.

if "%GOISO_DEBUG%"=="1" (
  set GOISO_PORT=5000
  python app.py
) else (
  waitress-serve --listen=127.0.0.1:5000 --threads=32 app:app
)
pause
