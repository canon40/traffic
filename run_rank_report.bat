@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [전체 순위 재조회] API 1000위 + stealth Playwright (순차 1브라우저)
echo   봇 회피: API 우선 / 키워드 간 휴식 / Captcha 대기 재시도
echo   창 표시: set RANK_DEEP_HEADLESS=0 후 실행
echo.
"%PY%" scan_and_apply_keyword_ranks.py --deep --no-cache --parallel 1
"%PY%" rank_entry_report.py --write
echo.
echo 완료: generated_content\rank_report_latest.txt
echo       data\rank_latest_summary.json
pause
