@echo off
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
"%PY%" weekly_rank_report.py --save
pause
