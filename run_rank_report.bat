@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [전체 순위 재조회] API 우선 + 딥스캔 (시간 소요)
echo.
"%PY%" scan_and_apply_keyword_ranks.py --deep --no-cache
"%PY%" rank_entry_report.py --write
echo.
echo 완료: generated_content\rank_report_latest.txt
echo       data\rank_latest_summary.json
pause
