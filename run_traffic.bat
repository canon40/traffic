@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================
echo  나눔랩 스마트스토어 트래픽 부스팅 시작
echo  (종료: Ctrl+C)
echo ====================================================
echo.
call "%~dp0_find_py.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)
echo [Python] %PYEXE%
"%PYEXE%" -m pip install -q playwright playwright-stealth pandas beautifulsoup4 requests
"%PYEXE%" -m playwright install chromium
echo.
"%PYEXE%" -u traffic_service.py %*
echo.
echo === 작업 완료 ===
pause
