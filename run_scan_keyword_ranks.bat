@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 전체 키워드 순위 스캔 및 config 반영...
echo.
echo 사용 예:
echo   기본(HTTP):     run_scan_keyword_ranks.bat
echo   딥스캔+병렬:    run_scan_keyword_ranks.bat --deep --parallel 3 --no-cache
echo   결과만 반영:    run_scan_keyword_ranks.bat --apply-only
echo.
C:\Users\hymin\AppData\Local\Python\bin\python.exe scan_and_apply_keyword_ranks.py %*
pause
