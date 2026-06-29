@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [진행도] 순위 진입 현황 (100위/TOP10/미진입)
"%PY%" rank_entry_report.py --print
pause
