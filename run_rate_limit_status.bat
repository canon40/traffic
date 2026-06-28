@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
"%PY%" -c "from traffic_rate_limit import get_state, status_summary; import json; s=get_state(); print(status_summary()); print(json.dumps(s, indent=2))"
pause
