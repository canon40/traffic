# -*- coding: utf-8 -*-
"""rank_history.csv 최신 순위 기준 — 발견 키워드만 config·traffic_config 반영."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "rank_history.csv"
CONFIG = ROOT / "config.json"
AUDIT = ROOT / "generated_content" / "rank_keyword_audit.json"
NOT_FOUND_RANK = 999
MAX_FOUND_RANK = 519

# (keyword, product_key, product_id, mode)
FOUND_TASKS = [
    ("듀라코트 리빙코트", "livingcoat", "10713170202", "maintain"),
    ("리빙코트", "livingcoat", "10713170202", "maintain"),
]

PRODUCTS = {
    "livingcoat": "https://smartstore.naver.com/nanumlab/products/10713170202",
}


def latest_ranks() -> dict[str, int]:
    if not HISTORY.exists():
        return {}
    latest: dict[str, int] = {}
    with HISTORY.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            kw = row.get("키워드", "").strip()
            if not kw:
                continue
            try:
                rank = int(row.get("순위", NOT_FOUND_RANK))
            except (TypeError, ValueError):
                rank = NOT_FOUND_RANK
            latest[kw] = rank
    return latest


def apply() -> dict:
    ranks = latest_ranks()
    found = []
    for kw, pk, pid, mode in FOUND_TASKS:
        rank = ranks.get(kw)
        found.append(
            {
                "keyword": kw,
                "product_key": pk,
                "product_id": pid,
                "mode": mode,
                "latest_rank": rank,
            }
        )

    removed = sorted(
        kw for kw, r in ranks.items() if r >= NOT_FOUND_RANK and kw not in {f[0] for f in FOUND_TASKS}
    )

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    store = cfg.get("store_name", "나눔랩")
    cfg["keywords"] = [
        {"keyword": kw, "store_name": store, "product_id": pid}
        for kw, _, pid, _ in FOUND_TASKS
    ]
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    keyword_tasks = [
        {
            "keyword": kw,
            "product_key": pk,
            "product_url": PRODUCTS[pk],
            "mode": mode,
            "priority": 3 if mode == "maintain" else 10,
        }
        for kw, pk, _, mode in FOUND_TASKS
    ]
    traffic = {
        "products": json.loads((ROOT / "traffic_config.json").read_text(encoding="utf-8")).get(
            "products", {}
        ),
        "target_urls": [PRODUCTS["livingcoat"]],
        "keywords": [kw for kw, _, _, _ in FOUND_TASKS],
        "keyword_tasks": keyword_tasks,
        "boost_sessions": 1,
        "maintain_sessions": 1,
        "max_pages": 10,
        "stay_time_range": [35, 55],
        "rate_limit": json.loads((ROOT / "traffic_config.json").read_text(encoding="utf-8")).get(
            "rate_limit",
            {
                "min_session_gap_sec": 120,
                "max_sessions_per_hour": 15,
                "cooldown_429_sec": 2700,
                "cooldown_429_escalated_sec": 5400,
                "escalate_after_consecutive_429": 3,
                "batch_size": 10,
                "batch_rest_sec": 1200,
            },
        ),
    }
    (ROOT / "traffic_config.json").write_text(
        json.dumps(traffic, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    focus_path = ROOT / "generated_content" / "candidate_keywords_focus.json"
    old_focus = json.loads(focus_path.read_text(encoding="utf-8")) if focus_path.exists() else {}
    archived_traffic = {
        "hot_zone": old_focus.get("hot_zone", []),
        "candidate_zone": old_focus.get("candidate_zone", []),
    }
    focus = {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "note": "전체 검색(520위)에서 확인된 키워드만 유지·순위 작업. hot/candidate는 archived.",
        "hot_zone": [],
        "candidate_zone": [],
        "maintain_only": [
            {
                "keyword": kw,
                "product_id": pid,
                "last_observed_rank": ranks.get(kw) if ranks.get(kw, NOT_FOUND_RANK) < NOT_FOUND_RANK else None,
                "sessions_per_cycle": 1,
            }
            for kw, _, pid, _ in FOUND_TASKS
        ],
    }
    focus_path.write_text(json.dumps(focus, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = {
        "updated_at": datetime.now().isoformat(),
        "criteria": "네이버 쇼핑 API 전체 검색(약 520위) — 순위 발견 시에만 추적",
        "found_rank_tracking": found,
        "removed_from_rank_tracking": removed,
        "archived_traffic_zones": archived_traffic,
        "summary": {
            "found_count": len(found),
            "removed_count": len(removed),
        },
    }
    AUDIT.parent.mkdir(exist_ok=True)
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    result = apply()
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print("found:", [x["keyword"] for x in result["found_rank_tracking"]])
    print(f"removed: {result['summary']['removed_count']} keywords → {AUDIT.name}")
