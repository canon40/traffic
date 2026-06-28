# -*- coding: utf-8 -*-
"""
매일 1회 순위 추적 → rank_history.csv 적재.
월요일(또는 --weekly)이면 주간 리포트도 자동 저장.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "daily_rank_track.log"
LOCK_FILE = ROOT / ".daily_rank_track.lock"

from rank_tracker import (  # noqa: E402
    build_completion_report,
    build_weekly_rank_report,
    save_weekly_report,
    track_all_keywords,
)


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="일일 순위 추적 (1회 실행)")
    parser.add_argument("--weekly", action="store_true", help="주간 리포트도 저장")
    parser.add_argument("--force", action="store_true", help="실행 잠금 무시")
    args = parser.parse_args()

    if LOCK_FILE.exists() and not args.force:
        log("이미 실행 중 — 건너뜀")
        return 0

    LOCK_FILE.write_text(datetime.now().isoformat(), encoding="utf-8")
    try:
        log("일일 순위 추적 시작")
        results = track_all_keywords(logger=log)
        report = build_completion_report(results)
        log(report["summary"])

        for item in report.get("items", []):
            status = item.get("status")
            if status in ("상승", "하락", "신규기록"):
                log(f"  [{status}] {item['keyword']}: {item.get('detail', '')}")

        snap_dir = ROOT / "generated_content"
        snap_dir.mkdir(exist_ok=True)
        snap = snap_dir / f"daily_rank_{datetime.now().strftime('%Y%m%d')}.json"
        with snap.open("w", encoding="utf-8") as f:
            json.dump(
                {"completed_at": datetime.now().isoformat(), "report": report},
                f,
                ensure_ascii=False,
                indent=2,
            )
        log(f"일일 스냅샷 저장: {snap.name}")

        if args.weekly or datetime.now().weekday() == 0:
            weekly = build_weekly_rank_report(days=7)
            json_path, csv_path = save_weekly_report(weekly)
            log(f"주간 리포트 저장: {Path(json_path).name}, {Path(csv_path).name}")
            log(weekly["summary"])

        log("완료")
        from scheduler_state import mark_success
        mark_success("daily_rank_track", report.get("summary", ""))
        try:
            from data_store import push_to_cloud
            push_to_cloud(("rank_history.csv",))
        except Exception:
            pass
        return 0
    except Exception as e:
        log(f"오류: {e}")
        return 1
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
