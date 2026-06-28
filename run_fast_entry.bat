@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
set TRAFFIC_SKIP_COMPETITORS=1
echo [0/3] playwright-stealth 확인...
"%PY%" -m pip install playwright-stealth -q
echo [1/3] traffic_config 재생성...
"%PY%" build_keyword_config.py
if errorlevel 1 exit /b 1
echo [2/3] 429 안전 모드 캠페인 (1라운드, 세션간격 120초+)
echo       시간당 15세션 / 10세션마다 20분 휴식
"%PY%" fast_entry_campaign.py --headless --rounds 1 --safe
pause
