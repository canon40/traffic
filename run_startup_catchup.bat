@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
if "%1"=="--silent" (
    "%PY%" startup_catchup.py >> startup_catchup.log 2>&1
    exit /b %errorlevel%
)
echo [로그인 보충] 오늘 안 한 순위 추적 등을 실행합니다...
"%PY%" startup_catchup.py
pause
