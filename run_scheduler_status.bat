@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === 스케줄 상태 ===
C:\Users\hymin\AppData\Local\Python\bin\python.exe -c "from scheduler_state import load_state; import json; print(json.dumps(load_state(), ensure_ascii=False, indent=2))"
echo.
echo === Windows 작업 ===
schtasks /query /tn "NanumLab-DailyRankTrack" /fo LIST 2>nul | findstr /i "TaskName Status Next"
schtasks /query /tn "NanumLab-StartupCatchup" /fo LIST 2>nul | findstr /i "TaskName Status Next"
pause
