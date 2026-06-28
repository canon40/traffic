@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [테스트] focus 부스팅 10세션 (headless)
"%PY%" focus_campaign.py --headless --limit 10
pause
