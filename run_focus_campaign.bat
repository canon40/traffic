@echo off
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [집중 캠페인] 후보권 키워드만 (11~70위 관측)
"%PY%" focus_campaign.py --dry-run
echo.
set /p RUN=실행하려면 Y 입력: 
if /i "%RUN%"=="Y" "%PY%" focus_campaign.py --headless
pause
