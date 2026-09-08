@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0server"
echo ================================================
echo   MAY CHU HE THONG GOI SO - CHI NHANH EA KAR
echo ================================================
echo   Man hinh hien thi : http://localhost:5000/display
echo   Ban goi so        : http://localhost:5000/counter
echo   Quan tri          : http://localhost:5000/admin
echo ------------------------------------------------
python -m pip install -q -r requirements.txt
set GOISO_PORT=5000
python app.py
pause
