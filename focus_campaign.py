# -*- coding: utf-8 -*-
"""
미발견/ Hot 키워드 집중 부스팅 (30위 내 진입 목표).

인프라:
  - run_tracked_session → traffic_service (웜업→검색 Referer→SERP→상품)
  - apply_wait / record_429 → traffic_rate_limit (429·시간당 한도)
  - 키워드 소스: generated_content/candidate_keywords_focus.json

세션 분배 (기본):
  entry 66×3=198 | hot 1×5=5 | maintain_boost 1×5=5 | maintain 1×1=1 → 209

실행: --dry-run | --limit N | --headless
Cloudtype(512MB): 순위 전용 — 본 스크립트는 로컬 PC / GCP VM 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from traffic_rate_limit import apply_wait, record_429, record_session_start
from traffic_session_log import run_tracked_session

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
FOCUS_FILE = ROOT / "generated_content" / "candidate_keywords_focus.json"
LOG_FILE = ROOT / "focus_campaign_log.jsonl"

# zone / boost_type → 세션 반복·체류(초)
ZONE_PROFILES: dict[str, dict] = {
    "entry": {"weight": 3, "stay": (45, 70), "boost_type": "entry_boost"},
    "hot": {"weight": 5, "stay": (60, 90), "boost_type": "hot_boost"},
    "candidate": {"weight": 1, "stay": (40, 60), "boost_type": "candidate_boost"},
    "maintain": {"weight": 1, "stay": (30, 45), "boost_type": "maintain"},
    "maintain_boost": {"weight": 5, "stay": (60, 90), "boost_type": "maintain_boost"},
}

# 키워드별 zone 오버라이드 (상위 방어 + 화력 집중)
KEYWORD_ZONE_OVERRIDE: dict[str, str] = {
    "듀라코트 리빙코트": "maintain_boost",
    "리빙코트": "hot",
    "퍼마코트 자동차 코팅제": "maintain",
}


def load_focus() -> dict:
    if not FOCUS_FILE.exists():
        raise FileNotFoundError(f"focus 설정 없음: {FOCUS_FILE}")
    with FOCUS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _product_url(item: dict) -> str:
    if item.get("product_url"):
        return item["product_url"]
    pid = item.get("product_id")
    if pid:
        return f"https://smartstore.naver.com/nanumlab/products/{pid}"
    return ""


def _profile_for(keyword: str, sessions_tag: str) -> dict:
    zone_key = KEYWORD_ZONE_OVERRIDE.get(keyword, sessions_tag)
    if zone_key not in ZONE_PROFILES:
        zone_key = "entry"
    return {**ZONE_PROFILES[zone_key], "zone_key": zone_key}


def build_weighted_queue(
    data: dict,
    *,
    entry_weight: int | None = None,
    hot_weight: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    """entry → hot → candidate → maintain 순으로 가중치 큐 생성."""
    queue: list[dict] = []

    def add_items(items: list[dict], default_tag: str) -> None:
        for item in items:
            kw = item.get("keyword", "")
            if not kw:
                continue
            prof = _profile_for(kw, default_tag)
            w = prof["weight"]
            if default_tag == "entry" and entry_weight is not None:
                w = entry_weight
            if default_tag == "hot" and hot_weight is not None:
                w = hot_weight
            base = {
                "keyword": kw,
                "product_url": _product_url(item),
                "last_observed_rank": item.get("last_observed_rank"),
                "priority": item.get("priority", 10),
                "sessions_tag": default_tag,
                "boost_type": prof["boost_type"],
                "zone_key": prof["zone_key"],
                "stay_range": prof["stay"],
                "weight": w,
            }
            for _ in range(w):
                queue.append(dict(base))

    # 1) 미발견 66 — 진입 최우선
    entry = sorted(data.get("entry_priority", []), key=lambda x: -x.get("priority", 0))
    add_items(entry, "entry")

    # 2) Hot (7~30위)
    hot = sorted(data.get("hot_zone", []), key=lambda x: -x.get("priority", 0))
    add_items(hot, "hot")

    # 3) Candidate (31~70위)
    cand = sorted(data.get("candidate_zone", []), key=lambda x: -x.get("priority", 0))
    add_items(cand, "candidate")

    # 4) Maintain / maintain_boost
    for m in data.get("maintain_only", []):
        kw = m.get("keyword", "")
        prof = _profile_for(kw, "maintain")
        base = {
            "keyword": kw,
            "product_url": _product_url(m),
            "last_observed_rank": m.get("last_observed_rank"),
            "priority": 3,
            "sessions_tag": prof["zone_key"],
            "boost_type": prof["boost_type"],
            "zone_key": prof["zone_key"],
            "stay_range": prof["stay"],
            "weight": prof["weight"],
        }
        for _ in range(prof["weight"]):
            queue.append(dict(base))

    random.shuffle(queue)
    if limit and limit > 0:
        queue = queue[:limit]
    return queue


def append_log(record: dict) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _gap_seconds(boost_type: str, detected: bool) -> float:
    if detected:
        return min(record_429(), 120)
    if boost_type in ("entry_boost", "hot_boost", "maintain_boost"):
        return random.uniform(90, 120)
    return random.uniform(120, 150)


def main() -> int:
    parser = argparse.ArgumentParser(description="미발견/Hot 키워드 가중치 부스팅")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--entry-weight", type=int, default=None, help="entry 세션 가중치 (기본 3)")
    parser.add_argument("--hot-weight", type=int, default=None, help="hot 세션 가중치 (기본 5)")
    parser.add_argument("--limit", type=int, default=0, help="최대 세션 수 (0=전체)")
    args = parser.parse_args()

    data = load_focus()
    limit = args.limit if args.limit > 0 else None
    queue = build_weighted_queue(
        data,
        entry_weight=args.entry_weight,
        hot_weight=args.hot_weight,
        limit=limit,
    )

    entry_n = len(data.get("entry_priority", []))
    hot_n = len(data.get("hot_zone", []))
    maintain_n = len(data.get("maintain_only", []))

    print("=" * 60)
    print("FOCUS BOOST — 30위 내 진입 / 상위 유지")
    print(f"  entry 키워드: {entry_n} (×weight {ZONE_PROFILES['entry']['weight']})")
    print(f"  hot: {hot_n} · maintain: {maintain_n}")
    print(f"  총 세션(가중치 적용): {len(queue)}")
    print("=" * 60)

    if args.dry_run:
        by_type: dict[str, int] = {}
        for t in queue:
            by_type[t["boost_type"]] = by_type.get(t["boost_type"], 0) + 1
        print("세션 분포:", by_type)
        for i, t in enumerate(queue[:40], 1):
            stay = t["stay_range"]
            print(
                f"  {i:3d}. [{t['boost_type']}] {t['keyword']} "
                f"체류{stay[0]}-{stay[1]}s 관측={t.get('last_observed_rank', 'None')}"
            )
        if len(queue) > 40:
            print(f"  ... 외 {len(queue) - 40}건")
        return 0

    cfg_path = ROOT / "traffic_config.json"
    target_urls: list[str] = []
    rate_cfg: dict = {}
    if cfg_path.exists():
        with cfg_path.open(encoding="utf-8") as f:
            tc = json.load(f)
        target_urls = tc.get("target_urls", [])
        rate_cfg = tc

    os.environ["TRAFFIC_SKIP_COMPETITORS"] = "1"

    rank_tracked: set[str] = set()
    stats = {"ok": 0, "429": 0, "fail": 0}

    for i, task in enumerate(queue, 1):
        kw = task["keyword"]
        stay_range = tuple(task["stay_range"])
        boost_type = task["boost_type"]

        print(
            f"\n[{i}/{len(queue)}] [{boost_type}] '{kw}' "
            f"체류 {stay_range[0]}-{stay_range[1]}s"
        )

        apply_wait(rate_cfg, logger=print)
        record_session_start()

        track_rank = kw not in rank_tracked
        if track_rank:
            rank_tracked.add(kw)

        result = run_tracked_session(
            campaign="focus",
            keyword=kw,
            product_url=task["product_url"],
            mode=boost_type,
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
                "boost_type": boost_type,
                "weight": task.get("weight"),
                "stay_range": list(stay_range),
                "observed_rank": task.get("last_observed_rank"),
                "status": status,
                "detected": detected,
                "session_record": rec,
            }
        )

        if detected:
            stats["429"] += 1
        elif status.startswith("ERROR"):
            stats["fail"] += 1
        else:
            stats["ok"] += 1

        print(f"  -> {status}")
        if rec.get("outcome"):
            print(f"  -> {rec['outcome']}")

        if i < len(queue):
            delay = _gap_seconds(boost_type, detected)
            print(f"  [wait] {delay:.0f}s")
            time.sleep(delay)

    print(f"\n완료 ok={stats['ok']} 429={stats['429']} fail={stats['fail']}")
    print(f"로그: {LOG_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
