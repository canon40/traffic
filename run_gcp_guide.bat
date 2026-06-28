@echo off
chcp 65001 >nul
echo GCP VM 24h 트래픽 — README 요약
echo.
echo [역할 분담]
echo   Cloudtype  — 순위/대시보드 (ENABLE_CLOUD_TRAFFIC=0)
echo   GCP VM     — focus_campaign.py Playwright 트래픽
echo.
echo [GCP 최초 1회]
echo   git clone https://github.com/canon40/traffic.git
echo   cd traffic
echo   bash scripts/gcp_traffic_24h.sh
echo.
echo [수동 screen]
echo   screen -S traffic_running
echo   python3 focus_campaign.py --headless
echo   Ctrl+A, D  (detach)
echo.
echo [재접속] screen -r traffic_running
echo [코드 갱신] git pull origin main
pause
