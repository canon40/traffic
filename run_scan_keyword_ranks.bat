@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 전체 키워드 순위 스캔 및 config 반영...
C:\Users\hymin\AppData\Local\Python\bin\python.exe scan_and_apply_keyword_ranks.py %*
pause
