# -*- coding: utf-8 -*-
"""
PC 켜짐/로그인 시 놓친 스케줄 작업 보충 실행.
- 일일 순위 추적: 오늘 아직 안 했으면 1회 실행
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
PY = sys.executable
LOG = ROOT / "startup_catchup.log"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_daily_rank() -> int:
    log("보충 실행: daily_rank_track.py")
    proc = subprocess.run(
        [PY, str(ROOT / "daily_rank_track.py")],
        cwd=str(ROOT),
        capture_output=False,
    )
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="놓친 스케줄 작업 보충")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from scheduler_state import is_done_today

    log("=== startup catchup ===")
    tasks_run = 0

    if is_done_today("daily_rank_track"):
        log("일일 순위 추적: 오늘 이미 완료 — 건너뜀")
    else:
        log("일일 순위 추적: 오늘 미실행 — 보충 필요")
        if args.dry_run:
            log("[dry-run] daily_rank_track.py 실행 예정")
        else:
            code = run_daily_rank()
            if code == 0:
                tasks_run += 1
                log("일일 순위 추적 보충 완료")
            else:
                log(f"일일 순위 추적 실패 (exit {code})")

    log(f"보충 작업 {tasks_run}건 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
