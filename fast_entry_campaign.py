# -*- coding: utf-8 -*-
"""
순위 진입 최단 경로: 미발견 키워드 전수 스윕 → 재집중 라운드.
유지 대상(1~6위)은 라운드당 1회만 실행.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path

from traffic_service import run_session

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


def wait_between_sessions(fast: bool, detected: bool) -> None:
    if detected:
        cooldown = random.uniform(240, 360)
        print(f"  [cooldown] 봇 감지 → {cooldown:.0f}s 대기")
        time.sleep(cooldown)
        return
    if fast:
        delay = random.uniform(45, 70)
    else:
        delay = random.gauss(50, 12)
        delay = max(25.0, delay)
    print(f"  [wait] {delay:.0f}s")
    time.sleep(delay)


def append_log(record: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="미발견 키워드 빠른 순위 진입 캠페인")
    parser.add_argument("--headless", action="store_true", help="헤드리스 실행")
    parser.add_argument("--rounds", type=int, default=2, help="스윕 라운드 수 (기본 2)")
    parser.add_argument("--fast", action="store_true", default=True, help="세션 간격 단축 (기본 ON)")
    parser.add_argument("--no-fast", action="store_true", help="세션 간격 일반 모드")
    parser.add_argument("--dry-run", action="store_true", help="큐만 출력")
    args = parser.parse_args()
    fast = args.fast and not args.no_fast

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
    print(f"  라운드: {args.rounds} | 간격: {'빠름(18~32s)' if fast else '일반'}")
    print("=" * 60)

    if args.dry_run:
        for i, t in enumerate(queue, 1):
            tag = "유지" if t["keyword"] in MAINTAIN_KEYWORDS else "진입"
            print(f"  {i:3d}. [{tag}] {t['keyword']}")
        return 0

    ok = fail = 0
    for i, task in enumerate(queue, 1):
        kw = task["keyword"]
        preferred = task["product_url"]
        tag = "유지" if kw in MAINTAIN_KEYWORDS else "진입"
        print(f"\n[{i}/{len(queue)}] [{tag}] '{kw}'")
        print("-" * 50)

        result = run_session(
            keyword=kw,
            target_store_id="nanumlab",
            target_urls=target_urls,
            headless=args.headless,
            stay_range=stay_range,
            preferred_url=preferred,
        )

        detected = bool(result.get("detected"))
        if result.get("target_found"):
            ok += 1
            status = "TARGET_FOUND"
        elif result.get("error"):
            fail += 1
            status = f"ERROR: {result['error']}"
        else:
            status = "FALLBACK"

        record = {
            "at": datetime.now().isoformat(),
            "keyword": kw,
            "mode": tag,
            "status": status,
            "target_found": result.get("target_found"),
            "detected": detected,
        }
        append_log(record)
        print(f"  → {status}")

        if i < len(queue):
            wait_between_sessions(fast, detected)

    print("\n" + "=" * 60)
    print(f"완료: 성공 {ok} / 실패 {fail} / 총 {len(queue)}세션")
    print(f"로그: {LOG_FILE}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
