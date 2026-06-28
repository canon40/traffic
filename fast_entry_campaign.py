# -*- coding: utf-8 -*-
"""
순위 진입 최단 경로: 미발견 키워드 전수 스윕 → 재집중 라운드.
유지 대상(1~6위)은 라운드당 1회만 실행.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

from traffic_session_log import run_tracked_session
from traffic_rate_limit import apply_wait, load_rate_config, record_429, record_session_start, status_summary

ROOT = Path(__file__).resolve().parent
TRAFFIC_CFG = ROOT / "traffic_config.json"
LOG_FILE = ROOT / "fast_entry_log.jsonl"

# 순위 유지 키워드 (라운드당 1세션)
MAINTAIN_KEYWORDS = frozenset(
    {
        "퍼마코트 자동차 코팅제",
        "듀라코트 리빙코트",
    }
)


def load_tasks() -> tuple[list[dict], dict]:
    with TRAFFIC_CFG.open(encoding="utf-8") as f:
        cfg = json.load(f)
    tasks = []
    for t in cfg.get("keyword_tasks", []):
        kw = str(t.get("keyword", "")).strip()
        url = str(t.get("product_url", "")).strip()
        if not kw or not url:
            continue
        tasks.append(
            {
                "keyword": kw,
                "product_url": url,
                "mode": t.get("mode", "boost"),
                "priority": int(t.get("priority", 5)),
            }
        )
    return tasks, cfg


def build_queue(tasks: list[dict], rounds: int, cfg: dict) -> list[dict]:
    """진입 키워드 전수 스윕(라운드당 1회) → 유지 키워드 1회."""
    entry = [t for t in tasks if t["keyword"] not in MAINTAIN_KEYWORDS and t.get("mode") != "maintain"]
    maintain = [t for t in tasks if t["keyword"] in MAINTAIN_KEYWORDS or t.get("mode") == "maintain"]

    entry.sort(key=lambda t: (-t.get("priority", 5), t["keyword"]))

    queue: list[dict] = []
    for _ in range(rounds):
        sweep = entry.copy()
        random.shuffle(sweep)
        queue.extend(sweep)
        queue.extend(maintain)
    return queue


def wait_between_sessions(fast: bool, safe: bool, detected: bool, cfg: dict) -> None:
    if detected:
        wait = record_429()
        print(f"  [cooldown] HTTP 429 → {wait // 60}분 쿨다운 등록")
        time.sleep(min(wait, 120))
        return
    limits = load_rate_config(cfg)
    if safe or not fast:
        delay = random.uniform(
            limits["min_session_gap_sec"] * 0.9,
            limits["min_session_gap_sec"] * 1.3,
        )
    elif fast:
        delay = random.uniform(90, 130)
    else:
        delay = random.gauss(70, 15)
        delay = max(60.0, delay)
    print(f"  [wait] {delay:.0f}s")
    time.sleep(delay)


def append_log(record: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="미발견 키워드 빠른 순위 진입 캠페인")
    parser.add_argument("--headless", action="store_true", help="헤드리스 실행")
    parser.add_argument("--rounds", type=int, default=1, help="스윕 라운드 수 (기본 1, 429 완화)")
    parser.add_argument("--fast", action="store_true", help="간격 단축 (90~130초, 429 위험)")
    parser.add_argument("--no-safe", action="store_true", help="안전 모드 끄기 (위험)")
    parser.add_argument("--dry-run", action="store_true", help="큐만 출력")
    args = parser.parse_args()
    safe = not args.no_safe
    fast = args.fast and not safe

    tasks, cfg = load_tasks()
    if not tasks:
        print("keyword_tasks 없음 — build_keyword_config.py 먼저 실행하세요.")
        return 1

    queue = build_queue(tasks, max(1, args.rounds), cfg)
    target_urls = cfg.get("target_urls", [])
    stay_range = tuple(cfg.get("stay_time_range", [45, 90]))
    entry_cnt = sum(1 for t in queue if t["keyword"] not in MAINTAIN_KEYWORDS)
    maintain_cnt = len(queue) - entry_cnt

    print("=" * 60)
    print("FAST ENTRY CAMPAIGN")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  키워드: 진입 {len(tasks) - len(MAINTAIN_KEYWORDS)} / 유지 {len(MAINTAIN_KEYWORDS)}")
    print(f"  큐: 총 {len(queue)}세션 (진입 {entry_cnt} + 유지 {maintain_cnt})")
    mode_label = "안전(120s+)" if safe else ("빠름(90s)" if fast else "일반(70s)")
    print(f"  라운드: {args.rounds} | 모드: {mode_label}")
    print(f"  {status_summary(cfg)}")
    print("=" * 60)

    if args.dry_run:
        for i, t in enumerate(queue, 1):
            tag = "유지" if t["keyword"] in MAINTAIN_KEYWORDS else "진입"
            print(f"  {i:3d}. [{tag}] {t['keyword']}")
        return 0

    ok = fail = 0
    rank_tracked: set[str] = set()
    os.environ["TRAFFIC_SKIP_COMPETITORS"] = "1" if safe else "0"
    for i, task in enumerate(queue, 1):
        kw = task["keyword"]
        preferred = task["product_url"]
        tag = "유지" if kw in MAINTAIN_KEYWORDS else "진입"
        print(f"\n[{i}/{len(queue)}] [{tag}] '{kw}'")
        print("-" * 50)

        apply_wait(cfg, logger=print)
        record_session_start()

        track_rank = kw not in rank_tracked
        if track_rank:
            rank_tracked.add(kw)

        result = run_tracked_session(
            campaign="fast_entry",
            keyword=kw,
            product_url=preferred,
            mode=tag,
            track_rank=track_rank,
            target_store_id="nanumlab",
            target_urls=target_urls,
            headless=args.headless,
            stay_range=stay_range,
        )

        detected = bool(result.get("detected"))
        status = result.get("status", "UNKNOWN")
        if result.get("target_found"):
            ok += 1
        elif result.get("error") or detected:
            fail += 1

        # legacy log 호환
        record = {
            "at": datetime.now().isoformat(),
            "keyword": kw,
            "mode": tag,
            "status": status,
            "target_found": result.get("target_found"),
            "detected": detected,
            "session_record": result.get("session_record"),
        }
        append_log(record)
        rec = result.get("session_record") or {}
        print(f"  → {status}")
        if rec.get("outcome"):
            print(f"  → {rec['outcome']}")

        if i < len(queue):
            wait_between_sessions(fast, safe, detected, cfg)

    print("\n" + "=" * 60)
    print(f"완료: 성공 {ok} / 실패 {fail} / 총 {len(queue)}세션")
    print(f"로그: {LOG_FILE}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
