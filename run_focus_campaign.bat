@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [집중 부스팅] entry×3 / hot×5 / maintain — 30위 진입
"%PY%" focus_campaign.py --dry-run
echo.
set /p RUN=실행하려면 Y 입력 (headless): 
if /i "%RUN%"=="Y" "%PY%" focus_campaign.py --headless
pause
