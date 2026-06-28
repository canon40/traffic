@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
"%PY%" traffic_campaign_report.py --save
pause
