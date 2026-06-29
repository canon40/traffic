@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [24h] focus_campaign 무한 루프 (headless, 사이클 간 30분)
echo 중단: Ctrl+C
"%PY%" focus_campaign.py --headless --loop --cycle-rest 1800
