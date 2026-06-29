@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [순위 부스팅] SEO 동기화 - 순위 추적 - 미진입 우선 트래픽 12회
echo.
echo [1/3] SEO 가이드/메타 동기화...
"%PY%" seo_fixes.py
echo.
echo [2/3] 순위 스캔 및 focus 반영...
"%PY%" scan_and_apply_keyword_ranks.py --no-cache
"%PY%" rank_entry_report.py --write
echo.
echo [3/3] 미진입 키워드 우선 트래픽 12세션...
"%PY%" focus_campaign.py --headless --limit 12
pause
