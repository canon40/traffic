# -*- coding: utf-8 -*-
"""미발견 키워드 목록 → traffic_config.json 생성 (진입 우선 / 유지 분리)."""
import json
from pathlib import Path

PRODUCTS = {
    "permacoat": "https://smartstore.naver.com/nanumlab/products/12639296730",
    "livingcoat": "https://smartstore.naver.com/nanumlab/products/10713170202",
    "coating_a": "https://smartstore.naver.com/nanumlab/products/12808820913",
    "coating_b": "https://smartstore.naver.com/nanumlab/products/12809519826",
    "coating_c": "https://smartstore.naver.com/nanumlab/products/12809532969",
    "coating_d": "https://smartstore.naver.com/nanumlab/products/12809541448",
    "cleaner": "https://smartstore.naver.com/nanumlab/products/12808787263",
    "coating_general": "https://smartstore.naver.com/nanumlab/products/12634187514",
    "product_e": "https://smartstore.naver.com/nanumlab/products/12634187514",
}

# (keyword, product_key, priority, mode) — 진입=boost priority 10, 유지=maintain priority 3
TASKS_RAW = [
    # ── 유지 (1~6위) ──
    ("퍼마코트 자동차 코팅제", "permacoat", 3, "maintain"),
    ("듀라코트 리빙코트", "livingcoat", 3, "maintain"),
    # ── 진입 우선 (미발견·신규기록) ──
    ("나눔랩 관련 상품 E", "product_e", 10, "boost"),
    ("발수코팅", "permacoat", 10, "boost"),
    ("광택", "permacoat", 10, "boost"),
    ("차량관리", "permacoat", 10, "boost"),
    ("자동차코팅", "permacoat", 10, "boost"),
    ("유리막", "permacoat", 10, "boost"),
    ("셀프코팅", "permacoat", 10, "boost"),
    ("나눔랩", "permacoat", 10, "boost"),
    ("셀프 유리막 코팅", "permacoat", 10, "boost"),
    ("퍼마코트 사용 후기", "permacoat", 10, "boost"),
    ("가구코팅 추천", "livingcoat", 10, "boost"),
    ("나눔랩 코팅제", "coating_a", 10, "boost"),
    ("유리막코팅제", "coating_a", 10, "boost"),
    ("나눔랩 세정제", "cleaner", 10, "boost"),
    ("자동차코팅제", "permacoat", 10, "boost"),
    ("리빙코트", "livingcoat", 10, "boost"),
    ("세차 관리제", "cleaner", 10, "boost"),
    ("나눔랩 코팅제", "coating_c", 10, "boost"),
    ("자동차 유리막코팅", "coating_c", 10, "boost"),
    ("나눔랩 코팅제", "coating_d", 10, "boost"),
    ("셀프 유리막코팅제", "coating_d", 10, "boost"),
    ("나눔랩 코팅제", "coating_b", 10, "boost"),
    ("유리막코팅제", "coating_b", 10, "boost"),
    ("나눔랩 코팅제", "coating_general", 10, "boost"),
    ("차량용 유리막코팅", "coating_general", 10, "boost"),
    ("리빙코트 처음 사용법", "livingcoat", 10, "boost"),
    ("리빙코트 원목", "livingcoat", 10, "boost"),
    ("나무 가구 실내코팅", "livingcoat", 10, "boost"),
    ("가구 리빙코트 방법", "livingcoat", 10, "boost"),
    ("가구코팅 가성비", "livingcoat", 10, "boost"),
    ("원목 리빙코트", "livingcoat", 10, "boost"),
    ("가구코팅 광택", "livingcoat", 10, "boost"),
    ("실내코팅 비추천 이유", "livingcoat", 10, "boost"),
    ("가구코팅 DIY", "livingcoat", 10, "boost"),
    ("가구코팅 주방", "livingcoat", 10, "boost"),
    ("가구코팅 가격 비교", "livingcoat", 10, "boost"),
    ("욕실 가구코팅", "livingcoat", 10, "boost"),
    ("실내코팅 원목", "livingcoat", 10, "boost"),
    ("가구코팅 욕실", "livingcoat", 10, "boost"),
    ("셀프 퍼마코트 순서", "permacoat", 10, "boost"),
    ("신차 자동차코팅제", "permacoat", 10, "boost"),
    ("유리막코팅 지속 기간", "permacoat", 10, "boost"),
    ("퍼마코트 가격 비교", "permacoat", 10, "boost"),
    ("퍼마코트 직접 해봤어요", "permacoat", 10, "boost"),
    ("자동차코팅제 직접", "permacoat", 10, "boost"),
    ("중고차 퍼마코트", "permacoat", 10, "boost"),
    ("쉬운 자동차코팅제", "permacoat", 10, "boost"),
    ("쉬운 자동차 코팅제 추천", "permacoat", 10, "boost"),
    ("유리막코팅 가격 비교", "permacoat", 10, "boost"),
    ("효과 자동차 코팅제 추천", "permacoat", 10, "boost"),
    ("자동차코팅제 직접 해봤어요", "permacoat", 10, "boost"),
    ("유리막코팅 가성비", "permacoat", 10, "boost"),
    ("자동차코팅제 가성비", "permacoat", 10, "boost"),
    ("신차 자동차코팅제", "coating_general", 10, "boost"),
    ("중고차 차량코팅제", "coating_general", 10, "boost"),
    ("셀프 차 코팅", "coating_general", 10, "boost"),
    ("쉬운 차량코팅제", "coating_general", 10, "boost"),
    ("유리막코팅제 가격 비교", "coating_general", 10, "boost"),
    ("자동차코팅제 직접", "coating_general", 10, "boost"),
    ("차량코팅제 직접", "coating_general", 10, "boost"),
    ("쉬운 자동차코팅제", "coating_general", 10, "boost"),
    ("신차 차 코팅", "coating_general", 10, "boost"),
    ("후기 유리막코팅제", "coating_general", 10, "boost"),
    ("차량코팅제 어떤게 좋아요", "coating_general", 10, "boost"),
    ("유리막코팅제 브랜드 비교", "coating_general", 10, "boost"),
    ("자동차코팅제 직접 해봤어요", "coating_general", 10, "boost"),
    ("자동차코팅제 효과 좋은", "coating_general", 10, "boost"),
    ("유리막코팅제 장마철", "coating_general", 10, "boost"),
]

keyword_tasks = []
seen = set()
for kw, pk, pri, mode in TASKS_RAW:
    key = (kw, pk)
    if key in seen:
        continue
    seen.add(key)
    keyword_tasks.append(
        {
            "keyword": kw,
            "product_key": pk,
            "product_url": PRODUCTS[pk],
            "mode": mode,
            "priority": pri,
        }
    )

cfg = {
    "products": PRODUCTS,
    "target_urls": list(dict.fromkeys(PRODUCTS.values())),
    "keywords": sorted({t["keyword"] for t in keyword_tasks}),
    "keyword_tasks": keyword_tasks,
    "boost_sessions": 2,
    "maintain_sessions": 1,
    "max_pages": 10,
    "stay_time_range": [35, 55],
    "rate_limit": {
        "min_session_gap_sec": 120,
        "max_sessions_per_hour": 15,
        "cooldown_429_sec": 2700,
        "cooldown_429_escalated_sec": 5400,
        "escalate_after_consecutive_429": 3,
        "batch_size": 10,
        "batch_rest_sec": 1200,
    },
}

Path("traffic_config.json").write_text(
    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
)
boost_n = sum(1 for t in keyword_tasks if t["mode"] == "boost")
maintain_n = sum(1 for t in keyword_tasks if t["mode"] == "maintain")
print(f"Wrote {len(keyword_tasks)} keyword_tasks (진입 {boost_n} / 유지 {maintain_n})")
