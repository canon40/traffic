# -*- coding: utf-8 -*-
"""
후보권(11~70위 관측) 키워드만 집중 트래픽.
429 완화: 세션 간격 90~120초, hot_zone 키워드당 2회, candidate 1회.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path

from traffic_session_log import run_tracked_session
from traffic_rate_limit import apply_wait, record_429, record_session_start, status_summary

ROOT = Path(__file__).resolve().parent
FOCUS_FILE = ROOT / "generated_content" / "candidate_keywords_focus.json"
LOG_FILE = ROOT / "focus_campaign_log.jsonl"


def load_focus() -> dict:
    with FOCUS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def build_queue(data: dict, hot_sessions: int = 2, candidate_sessions: int = 1) -> list[dict]:
    queue: list[dict] = []
    hot = sorted(data.get("hot_zone", []), key=lambda x: -x.get("priority", 0))
    cand = sorted(data.get("candidate_zone", []), key=lambda x: -x.get("priority", 0))

    for item in hot:
        for _ in range(hot_sessions):
            queue.append({**item, "sessions_tag": "hot"})
    random.shuffle(queue)

    cand_queue: list[dict] = []
    for item in cand:
        for _ in range(candidate_sessions):
            cand_queue.append({**item, "sessions_tag": "candidate"})
    random.shuffle(cand_queue)
    queue.extend(cand_queue)

    for m in data.get("maintain_only", []):
        queue.append(
            {
                "keyword": m["keyword"],
                "product_url": f"https://smartstore.naver.com/nanumlab/products/{m['product_id']}",
                "priority": 3,
                "sessions_tag": "maintain",
                "last_observed_rank": m.get("last_observed_rank"),
            }
        )
    return queue


def append_log(record: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="후보권 키워드 집중 캠페인")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hot-sessions", type=int, default=2)
    parser.add_argument("--candidate-sessions", type=int, default=1)
    args = parser.parse_args()

    data = load_focus()
    queue = build_queue(data, args.hot_sessions, args.candidate_sessions)

    print("=" * 60)
    print("FOCUS CAMPAIGN (후보권 집중)")
    print(f"  hot: {len(data.get('hot_zone', []))} kw x {args.hot_sessions}")
    print(f"  candidate: {len(data.get('candidate_zone', []))} kw x {args.candidate_sessions}")
    print(f"  총 세션: {len(queue)}")
    print("=" * 60)

    if args.dry_run:
        for i, t in enumerate(queue, 1):
            print(
                f"  {i:2d}. [{t.get('sessions_tag')}] {t['keyword']} "
                f"(관측 {t.get('last_observed_rank', '-')}위)"
            )
        return 0

    cfg_path = ROOT / "traffic_config.json"
    target_urls = []
    stay_range = (28, 50)
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            tc = json.load(f)
        target_urls = tc.get("target_urls", [])
        stay_range = tuple(tc.get("stay_time_range", [28, 50]))
        rate_cfg = tc
    else:
        rate_cfg = {}

    import os
    os.environ["TRAFFIC_SKIP_COMPETITORS"] = "1"

    rank_tracked: set[str] = set()
    for i, task in enumerate(queue, 1):
        kw = task["keyword"]
        preferred = task["product_url"]
        print(f"\n[{i}/{len(queue)}] [{task.get('sessions_tag')}] '{kw}'")

        apply_wait(rate_cfg, logger=print)
        record_session_start()

        track_rank = kw not in rank_tracked
        if track_rank:
            rank_tracked.add(kw)

        result = run_tracked_session(
            campaign="focus",
            keyword=kw,
            product_url=preferred,
            mode=task.get("sessions_tag", ""),
            track_rank=track_rank,
            target_store_id="nanumlab",
            target_urls=target_urls,
            headless=args.headless,
            stay_range=stay_range,
        )

        detected = bool(result.get("detected"))
        status = result.get("status", "UNKNOWN")
        rec = result.get("session_record") or {}
        append_log(
            {
                "at": datetime.now().isoformat(),
                "keyword": kw,
                "zone": task.get("sessions_tag"),
                "observed_rank": task.get("last_observed_rank"),
                "status": status,
                "detected": detected,
                "session_record": rec,
            }
        )
        print(f"  -> {status}")
        if rec.get("outcome"):
            print(f"  -> {rec['outcome']}")

        if i < len(queue) and not detected:
            delay = random.uniform(120, 150)
            print(f"  [wait] {delay:.0f}s")
            time.sleep(delay)
        elif detected:
            wait = record_429()
            print(f"  [cooldown] 429 → {wait // 60}분 등록, 2분 대기 후 종료 권장")
            time.sleep(min(wait, 120))

    print(f"\n완료. 로그: {LOG_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
