@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [run_full_ui] Browser + URL input mode...
python smartstore_monitor_and_editor.py
echo.
pause
