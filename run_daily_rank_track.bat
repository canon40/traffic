@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe

if "%1"=="--silent" (
    "%PY%" daily_rank_track.py >> daily_rank_track.log 2>&1
    exit /b %errorlevel%
)

echo ====================================================
echo  나눔랩 일일 순위 추적 (config.json 키워드 전체)
echo  기록: rank_history.csv
echo ====================================================
echo.
"%PY%" daily_rank_track.py %*
echo.
if not "%1"=="--no-pause" pause
