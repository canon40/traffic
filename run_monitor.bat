@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [run_monitor] keyword monitoring...
python smartstore_monitor_and_editor.py --monitor-only
echo.
pause
