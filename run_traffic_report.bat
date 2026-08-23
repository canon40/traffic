@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0_find_py.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)
"%PYEXE%" traffic_campaign_report.py --save
pause
