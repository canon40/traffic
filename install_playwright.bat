@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe"
if not exist "%PY%" set "PY=python"
echo [Playwright] 딥스캔용 Chromium 설치
echo Python: %PY%
echo.
"%PY%" -m pip install playwright playwright-stealth
if errorlevel 1 exit /b 1
"%PY%" -m playwright install chromium
if errorlevel 1 exit /b 1
echo.
echo 완료. run_rank_report.bat 실행 가능합니다.
pause
