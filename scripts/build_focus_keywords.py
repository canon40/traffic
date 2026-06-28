# -*- coding: utf-8 -*-
"""candidate_keywords_focus.json 생성 — 키워드×상품 매핑."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "generated_content" / "candidate_keywords_focus.json"

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

# (keyword, product_key) — 중복 키워드는 대표 상품 1개
ENTRY_CATALOG = [
    ("발수코팅", "permacoat"), ("광택", "permacoat"), ("차량관리", "permacoat"),
    ("자동차코팅", "permacoat"), ("유리막", "permacoat"), ("셀프코팅", "permacoat"),
    ("나눔랩", "permacoat"), ("셀프 유리막 코팅", "permacoat"), ("퍼마코트 사용 후기", "permacoat"),
    ("자동차코팅제", "permacoat"), ("셀프 퍼마코트 순서", "permacoat"),
    ("신차 자동차코팅제", "permacoat"), ("유리막코팅 지속 기간", "permacoat"),
    ("퍼마코트 가격 비교", "permacoat"), ("퍼마코트 직접 해봤어요", "permacoat"),
    ("자동차코팅제 직접", "permacoat"), ("중고차 퍼마코트", "permacoat"),
    ("쉬운 자동차코팅제", "permacoat"), ("쉬운 자동차 코팅제 추천", "permacoat"),
    ("유리막코팅 가격 비교", "permacoat"), ("효과 자동차 코팅제 추천", "permacoat"),
    ("자동차코팅제 직접 해봤어요", "permacoat"), ("유리막코팅 가성비", "permacoat"),
    ("자동차코팅제 가성비", "permacoat"),
    ("가구코팅 추천", "livingcoat"), ("리빙코트 처음 사용법", "livingcoat"),
    ("리빙코트 원목", "livingcoat"), ("나무 가구 실내코팅", "livingcoat"),
    ("가구 리빙코트 방법", "livingcoat"), ("가구코팅 가성비", "livingcoat"),
    ("원목 리빙코트", "livingcoat"), ("가구코팅 광택", "livingcoat"),
    ("실내코팅 비추천 이유", "livingcoat"), ("가구코팅 DIY", "livingcoat"),
    ("가구코팅 주방", "livingcoat"), ("가구코팅 가격 비교", "livingcoat"),
    ("욕실 가구코팅", "livingcoat"), ("실내코팅 원목", "livingcoat"),
    ("가구코팅 욕실", "livingcoat"),
    ("나눔랩 코팅제", "coating_a"), ("유리막코팅제", "coating_a"),
    ("나눔랩 세정제", "cleaner"), ("세차 관리제", "cleaner"),
    ("자동차 유리막코팅", "coating_c"), ("셀프 유리막코팅제", "coating_d"),
    ("차량용 유리막코팅", "coating_general"), ("중고차 차량코팅제", "coating_general"),
    ("셀프 차 코팅", "coating_general"), ("쉬운 차량코팅제", "coating_general"),
    ("유리막코팅제 가격 비교", "coating_general"), ("차량코팅제 직접", "coating_general"),
    ("신차 차 코팅", "coating_general"), ("후기 유리막코팅제", "coating_general"),
    ("차량코팅제 어떤게 좋아요", "coating_general"),
    ("유리막코팅제 브랜드 비교", "coating_general"),
    ("자동차코팅제 효과 좋은", "coating_general"), ("유리막코팅제 장마철", "coating_general"),
]


def _item(keyword: str, pk: str, rank=None, priority: int = 10) -> dict:
    pid, url = PRODUCTS[pk]
    return {
        "keyword": keyword,
        "product_id": pid,
        "product_url": url,
        "last_observed_rank": rank,
        "priority": priority,
    }


def build() -> dict:
    seen: set[str] = set()
    entry: list[dict] = []
    for kw, pk in ENTRY_CATALOG:
        if kw in seen:
            continue
        seen.add(kw)
        entry.append(_item(kw, pk))

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "note": "미발견 entry_priority + hot 리빙코트 + maintain 듀라코트/퍼마코트",
        "entry_priority": entry,
        "hot_zone": [_item("리빙코트", "livingcoat", 13, 12)],
        "candidate_zone": [],
        "maintain_only": [
            {**_item("퍼마코트 자동차 코팅제", "permacoat", 5, 3), "sessions_per_cycle": 1},
            {**_item("듀라코트 리빙코트", "livingcoat", 6, 3), "sessions_per_cycle": 1},
        ],
    }


def main() -> int:
    data = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n = len(data["entry_priority"])
    print(f"Wrote {OUT.name}: entry {n} → {n * 3 + 5 + 5 + 1} weighted sessions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
