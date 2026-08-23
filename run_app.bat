@echo off
chcp 65001 >nul
cd /d "%~dp0"
set AUTO_START_BACKGROUND=1
set AUTO_START_SCHEDULER=1
set ENABLE_CLOUD_TRAFFIC=0
set ENABLE_CLOUD_RANK_SWEEP=1
call "%~dp0_find_py.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)
echo ====================================================
echo  나눔랩 트래픽 대시보드 (로컬)
echo  http://127.0.0.1:5000
echo  종료: Ctrl+C
echo ====================================================
echo.
"%PYEXE%" app.py
pause
