@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0kiosk"
python -m pip install -q -r requirements.txt
python kiosk.py
pause
