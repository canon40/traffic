@echo off
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [1/2] traffic_config 재생성...
"%PY%" build_keyword_config.py
if errorlevel 1 exit /b 1
echo [2/2] 빠른 진입 캠페인 시작 (headless, 2라운드)...
"%PY%" fast_entry_campaign.py --headless --rounds 2 --fast
pause
