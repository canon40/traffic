# -*- coding: utf-8 -*-
"""전체 키워드×상품 순위 스캔 후 config·traffic·focus 반영."""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from rank_tracker import NOT_FOUND_RANK, append_history, check_product_rank

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
        sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass


def _log(msg: str) -> None:
    text = re.sub(r"[^\x00-\x7F\uAC00-\uD7A3\u3131-\u318E\s\[\]→위미발견.:…\-0-9]", "", msg)
    print(text, flush=True)

ROOT = Path(__file__).resolve().parent
SCAN_OUT = ROOT / "generated_content" / "keyword_rank_scan.json"
MAINTAIN_MAX_RANK = 6
HOT_MAX_RANK = 30
CANDIDATE_MAX_RANK = 70
SCAN_DELAY_SEC = 2.0

PRODUCTS = {
    "permacoat": ("12639296730", "https://smartstore.naver.com/nanumlab/products/12639296730"),
    "livingcoat": ("10713170202", "https://smartstore.naver.com/nanumlab/products/10713170202"),
    "coating_a": ("12808820913", "https://smartstore.naver.com/nanumlab/products/12808820913"),
    "coating_b": ("12809519826", "https://smartstore.naver.com/nanumlab/products/12809519826"),
    "coating_c": ("12809532969", "https://smartstore.naver.com/nanumlab/products/12809532969"),
    "coating_d": ("12809541448", "https://smartstore.naver.com/nanumlab/products/12809541448"),
    "cleaner": ("12808787263", "https://smartstore.naver.com/nanumlab/products/12808787263"),
    "coating_general": ("12634187514", "https://smartstore.naver.com/nanumlab/products/12634187514"),
}

# (keyword, product_key) — 대시보드·캠페인 전체 목록
KEYWORD_CATALOG = [
    ("발수코팅", "permacoat"),
    ("광택", "permacoat"),
    ("차량관리", "permacoat"),
    ("자동차코팅", "permacoat"),
    ("유리막", "permacoat"),
    ("셀프코팅", "permacoat"),
    ("나눔랩", "permacoat"),
    ("셀프 유리막 코팅", "permacoat"),
    ("퍼마코트 사용 후기", "permacoat"),
    ("자동차코팅제", "permacoat"),
    ("셀프 퍼마코트 순서", "permacoat"),
    ("신차 자동차코팅제", "permacoat"),
    ("유리막코팅 지속 기간", "permacoat"),
    ("퍼마코트 가격 비교", "permacoat"),
    ("퍼마코트 직접 해봤어요", "permacoat"),
    ("자동차코팅제 직접", "permacoat"),
    ("중고차 퍼마코트", "permacoat"),
    ("쉬운 자동차코팅제", "permacoat"),
    ("쉬운 자동차 코팅제 추천", "permacoat"),
    ("유리막코팅 가격 비교", "permacoat"),
    ("효과 자동차 코팅제 추천", "permacoat"),
    ("자동차코팅제 직접 해봤어요", "permacoat"),
    ("유리막코팅 가성비", "permacoat"),
    ("자동차코팅제 가성비", "permacoat"),
    ("퍼마코트 자동차 코팅제", "permacoat"),
    ("가구코팅 추천", "livingcoat"),
    ("리빙코트", "livingcoat"),
    ("리빙코트 처음 사용법", "livingcoat"),
    ("리빙코트 원목", "livingcoat"),
    ("나무 가구 실내코팅", "livingcoat"),
    ("가구 리빙코트 방법", "livingcoat"),
    ("가구코팅 가성비", "livingcoat"),
    ("원목 리빙코트", "livingcoat"),
    ("가구코팅 광택", "livingcoat"),
    ("실내코팅 비추천 이유", "livingcoat"),
    ("가구코팅 DIY", "livingcoat"),
    ("가구코팅 주방", "livingcoat"),
    ("가구코팅 가격 비교", "livingcoat"),
    ("욕실 가구코팅", "livingcoat"),
    ("실내코팅 원목", "livingcoat"),
    ("가구코팅 욕실", "livingcoat"),
    ("듀라코트 리빙코트", "livingcoat"),
    ("나눔랩 코팅제", "coating_a"),
    ("유리막코팅제", "coating_a"),
    ("나눔랩 세정제", "cleaner"),
    ("세차 관리제", "cleaner"),
    ("나눔랩 코팅제", "coating_c"),
    ("자동차 유리막코팅", "coating_c"),
    ("나눔랩 코팅제", "coating_d"),
    ("셀프 유리막코팅제", "coating_d"),
    ("나눔랩 코팅제", "coating_b"),
    ("유리막코팅제", "coating_b"),
    ("나눔랩 코팅제", "coating_general"),
    ("차량용 유리막코팅", "coating_general"),
    ("신차 자동차코팅제", "coating_general"),
    ("중고차 차량코팅제", "coating_general"),
    ("셀프 차 코팅", "coating_general"),
    ("쉬운 차량코팅제", "coating_general"),
    ("유리막코팅제 가격 비교", "coating_general"),
    ("자동차코팅제 직접", "coating_general"),
    ("차량코팅제 직접", "coating_general"),
    ("쉬운 자동차코팅제", "coating_general"),
    ("신차 차 코팅", "coating_general"),
    ("후기 유리막코팅제", "coating_general"),
    ("차량코팅제 어떤게 좋아요", "coating_general"),
    ("유리막코팅제 브랜드 비교", "coating_general"),
    ("자동차코팅제 직접 해봤어요", "coating_general"),
    ("자동차코팅제 효과 좋은", "coating_general"),
    ("유리막코팅제 장마철", "coating_general"),
]

# 대시보드에서 확인된 순위 (스캔 전 시드)
KNOWN_RANKS: dict[tuple[str, str], int] = {
    ("퍼마코트 자동차 코팅제", "permacoat"): 5,
    ("듀라코트 리빙코트", "livingcoat"): 6,
    ("리빙코트", "livingcoat"): 13,
}


def _load_history_ranks() -> dict[tuple[str, str], int]:
    """rank_history.csv 최신 순위 (키워드만 — livingcoat/permacoat 매핑)."""
    import csv

    path = ROOT / "rank_history.csv"
    if not path.exists():
        return {}
    product_by_keyword: dict[str, str] = {}
    for kw, pk in KEYWORD_CATALOG:
        product_by_keyword.setdefault(kw, pk)

    latest: dict[str, int] = {}
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            kw = row.get("키워드", "").strip()
            if not kw:
                continue
            try:
                latest[kw] = int(row.get("순위", NOT_FOUND_RANK))
            except (TypeError, ValueError):
                pass

    out: dict[tuple[str, str], int] = {}
    for kw, rank in latest.items():
        if rank >= NOT_FOUND_RANK:
            continue
        pk = product_by_keyword.get(kw)
        if pk:
            out[(kw, pk)] = rank
    return out


def _merge_rank(keyword: str, pk: str, scanned: int | None) -> int | None:
    if (keyword, pk) in KNOWN_RANKS:
        return KNOWN_RANKS[(keyword, pk)]
    hist = _load_history_ranks()
    if (keyword, pk) in hist:
        return hist[(keyword, pk)]
    return scanned


def _task_id(keyword: str, product_key: str) -> str:
    pid, _ = PRODUCTS[product_key]
    return f"{keyword}|{pid}"


def _mode_for_rank(rank: int | None) -> str:
    if rank is None or rank >= NOT_FOUND_RANK:
        return "boost"
    if rank <= MAINTAIN_MAX_RANK:
        return "maintain"
    return "boost"


def _zone_for_rank(rank: int | None) -> str:
    if rank is None or rank >= NOT_FOUND_RANK:
        return "entry"
    if rank <= MAINTAIN_MAX_RANK:
        return "maintain"
    if rank <= HOT_MAX_RANK:
        return "hot"
    if rank <= CANDIDATE_MAX_RANK:
        return "candidate"
    return "entry"


def reconcile_items(items: list[dict]) -> list[dict]:
    """캐시/스캔 결과에 히스토리·시드 순위 병합."""
    out = []
    for it in items:
        kw, pk = it["keyword"], it["product_key"]
        rank = _merge_rank(kw, pk, it.get("rank"))
        it = {**it, "rank": rank, "stored_rank": NOT_FOUND_RANK if rank is None else rank}
        it["mode"] = _mode_for_rank(rank)
        it["zone"] = _zone_for_rank(rank)
        out.append(it)
    return out


def scan_all(*, use_cache: bool = True, max_pages: int = 13) -> list[dict]:
    if use_cache and SCAN_OUT.exists():
        data = json.loads(SCAN_OUT.read_text(encoding="utf-8"))
        age_h = (datetime.now() - datetime.fromisoformat(data["scanned_at"])).total_seconds() / 3600
        if age_h < 12 and data.get("items"):
            print(f"캐시 사용 ({age_h:.1f}h 전 스캔, {len(data['items'])}건)")
            return reconcile_items(data["items"])

    seen: set[tuple[str, str]] = set()
    items: list[dict] = []
    total = len(KEYWORD_CATALOG)

    for i, (keyword, pk) in enumerate(KEYWORD_CATALOG, 1):
        key = (keyword, pk)
        if key in seen:
            continue
        seen.add(key)

        pid, url = PRODUCTS[pk]
        print(f"[{i}/{total}] {keyword} ({pk}) …", flush=True)
        seed = KNOWN_RANKS.get(key)
        scanned = None
        if seed is None:
            time.sleep(SCAN_DELAY_SEC)
            scanned = check_product_rank(keyword, pid, logger=_log, max_pages=max_pages)
        rank = _merge_rank(keyword, pk, scanned if seed is None else seed)

        stored_rank = NOT_FOUND_RANK if rank is None else rank
        mode = _mode_for_rank(rank)
        zone = _zone_for_rank(rank)

        item = {
            "keyword": keyword,
            "product_key": pk,
            "product_id": pid,
            "product_url": url,
            "rank": rank,
            "stored_rank": stored_rank,
            "mode": mode,
            "zone": zone,
            "task_id": _task_id(keyword, pk),
        }
        items.append(item)
        status = f"{rank}위" if rank else "미발견"
        print(f"  → {status} ({mode})", flush=True)

    items = reconcile_items(items)
    SCAN_OUT.parent.mkdir(exist_ok=True)
    SCAN_OUT.write_text(
        json.dumps(
            {"scanned_at": datetime.now().isoformat(), "items": items},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return items


def apply_scan(items: list[dict], *, record_history: bool = True) -> dict:
    store = "나눔랩"
    cfg_path = ROOT / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    cfg["keywords"] = [
        {"keyword": it["keyword"], "store_name": store, "product_id": it["product_id"]}
        for it in items
    ]
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    product_urls = {pk: url for pk, (_, url) in PRODUCTS.items()}
    all_products = {pk: url for pk, (pid, url) in PRODUCTS.items()}

    keyword_tasks = [
        {
            "keyword": it["keyword"],
            "product_key": it["product_key"],
            "product_url": it["product_url"],
            "mode": it["mode"],
            "priority": 3 if it["mode"] == "maintain" else 10,
            "last_rank": it["rank"],
            "zone": it["zone"],
        }
        for it in items
    ]

    traffic_path = ROOT / "traffic_config.json"
    traffic = json.loads(traffic_path.read_text(encoding="utf-8"))
    traffic["products"] = all_products
    traffic["target_urls"] = list(dict.fromkeys(all_products.values()))
    traffic["keywords"] = sorted({it["keyword"] for it in items})
    traffic["keyword_tasks"] = keyword_tasks
    traffic["boost_sessions"] = 2
    traffic["maintain_sessions"] = 1
    traffic_path.write_text(json.dumps(traffic, ensure_ascii=False, indent=2), encoding="utf-8")

    maintain_only, hot_zone, candidate_zone, entry_boost = [], [], [], []
    for it in items:
        row = {
            "keyword": it["keyword"],
            "product_id": it["product_id"],
            "product_url": it["product_url"],
            "last_observed_rank": it["rank"],
            "priority": 3 if it["zone"] == "maintain" else 10,
        }
        if it["zone"] == "maintain":
            row["sessions_per_cycle"] = 1
            maintain_only.append(row)
        elif it["zone"] == "hot":
            row["priority"] = 12
            hot_zone.append(row)
        elif it["zone"] == "candidate":
            row["priority"] = 9
            candidate_zone.append(row)
        else:
            entry_boost.append(row)

    focus = {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "note": "스캔 순위 기준: 1~6위 유지, 7~30 hot, 31~70 candidate, 미발견=진입 boost",
        "maintain_only": maintain_only,
        "hot_zone": sorted(hot_zone, key=lambda x: x.get("last_observed_rank") or 999),
        "candidate_zone": sorted(candidate_zone, key=lambda x: x.get("last_observed_rank") or 999),
        "entry_priority": sorted(entry_boost, key=lambda x: -x["priority"]),
    }
    focus_path = ROOT / "generated_content" / "candidate_keywords_focus.json"
    focus_path.write_text(json.dumps(focus, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = {
        "updated_at": datetime.now().isoformat(),
        "criteria": f"상품ID 기준 전체 검색(최대 {70}위 구간 집중 트래픽)",
        "maintain_max_rank": MAINTAIN_MAX_RANK,
        "found_rank_tracking": [it for it in items if it["rank"]],
        "entry_boost": [it for it in items if it["zone"] == "entry"],
        "hot_zone": hot_zone,
        "candidate_zone": candidate_zone,
        "maintain": maintain_only,
        "summary": {
            "total": len(items),
            "found": sum(1 for it in items if it["rank"]),
            "maintain": len(maintain_only),
            "hot": len(hot_zone),
            "candidate": len(candidate_zone),
            "entry": len(entry_boost),
        },
    }
    audit_path = ROOT / "generated_content" / "rank_keyword_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    if record_history:
        for it in items:
            rank = it["stored_rank"]
            detail = f"스캔: {it['rank']}위" if it["rank"] else "미발견 (520위 초과)"
            append_history(it["keyword"], store, rank, None, "순위스캔", detail)

    return audit


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--apply-only", action="store_true", help="캐시 스캔 결과만 반영")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--quick", action="store_true", help="시드+캐시만 (네트워크 스캔 생략)")
    args = p.parse_args()

    if args.apply_only:
        items = reconcile_items(json.loads(SCAN_OUT.read_text(encoding="utf-8"))["items"])
    elif args.quick:
        items = []
        seen = set()
        for keyword, pk in KEYWORD_CATALOG:
            if (keyword, pk) in seen:
                continue
            seen.add((keyword, pk))
            pid, url = PRODUCTS[pk]
            seed = KNOWN_RANKS.get((keyword, pk))
            rank = seed
            items.append(
                {
                    "keyword": keyword,
                    "product_key": pk,
                    "product_id": pid,
                    "product_url": url,
                    "rank": rank,
                    "stored_rank": NOT_FOUND_RANK if rank is None else rank,
                    "mode": _mode_for_rank(rank),
                    "zone": _zone_for_rank(rank),
                    "task_id": _task_id(keyword, pk),
                }
            )
    else:
        items = scan_all(use_cache=not args.no_cache)

    audit = apply_scan(items)
    s = audit["summary"]
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
