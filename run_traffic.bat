@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ====================================================
echo  나눔랩 스마트스토어 트래픽 부스팅 시작
echo  (종료: Ctrl+C)
echo ====================================================
echo.
python -u smartstore_monitor_and_editor.py
echo.
echo === 작업 완료 ===
pause
