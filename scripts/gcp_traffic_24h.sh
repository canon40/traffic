#!/usr/bin/env bash
# GCP VM — focus_campaign 24h headless (Ubuntu/Debian)
# 사용: bash scripts/gcp_traffic_24h.sh
set -euo pipefail

REPO="${TRAFFIC_REPO:-$HOME/traffic}"
SESSION_NAME="${SCREEN_SESSION:-traffic_running}"
PY="${PYTHON:-python3}"

echo "=== GCP 트래픽 24h 설정 ==="

if [[ ! -d "$REPO/.git" ]]; then
  git clone https://github.com/canon40/traffic.git "$REPO"
fi
cd "$REPO"
git pull origin main

$PY -m pip install -r requirements.txt
$PY -m playwright install
$PY -m playwright install-deps

if screen -list | grep -q "\.${SESSION_NAME}\s"; then
  echo "이미 screen 세션 '$SESSION_NAME' 존재 — attach: screen -r $SESSION_NAME"
  exit 0
fi

echo ""
echo "screen 세션 '$SESSION_NAME' 생성 후 focus_campaign 시작..."
echo "분리(detach): Ctrl+A, D  |  재접속: screen -r $SESSION_NAME"
echo ""

screen -dmS "$SESSION_NAME" bash -lc "
  cd '$REPO' &&
  $PY focus_campaign.py --headless 2>&1 | tee -a focus_campaign_gcp.log
"

sleep 1
screen -list | grep "$SESSION_NAME" || true
echo "=== 백그라운드 가동 시작 (로그: $REPO/focus_campaign_gcp.log) ==="
