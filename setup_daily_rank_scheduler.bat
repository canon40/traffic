@echo off
chcp 65001 >nul
cd /d "%~dp0"
C:\Users\hymin\AppData\Local\Python\bin\python.exe register_schedulers.py
pause
