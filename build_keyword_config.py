# -*- coding: utf-8 -*-
"""사용자 제공 미발견 키워드 목록 → traffic_config.json 생성."""
import json
from pathlib import Path

PRODUCTS = {
    "permacoat": "https://smartstore.naver.com/nanumlab/products/12639296730",
    "livingcoat": "https://smartstore.naver.com/nanumlab/products/10713170202",
    "coating_a": "https://smartstore.naver.com/nanumlab/products/12808820913",
    "coating_b": "https://smartstore.naver.com/nanumlab/products/12808787263",
    "coating_c": "https://smartstore.naver.com/nanumlab/products/12809532969",
    "coating_d": "https://smartstore.naver.com/nanumlab/products/12809541448",
    "cleaner": "https://smartstore.naver.com/nanumlab/products/12809519826",
    "coating_general": "https://smartstore.naver.com/nanumlab/products/12634187514",
    "product_e": "https://smartstore.naver.com/nanumlab/products/12634187514",
}

# (keyword, product_key, priority) — 신규기록/미발견은 priority 9
TASKS_RAW = [
    ("나눔랩 관련 상품 E", "product_e", 9),
    ("발수코팅", "permacoat", 7),
    ("광택", "permacoat", 7),
    ("차량관리", "permacoat", 7),
    ("자동차코팅", "permacoat", 7),
    ("유리막", "permacoat", 7),
    ("셀프코팅", "permacoat", 7),
    ("나눔랩", "permacoat", 7),
    ("셀프 유리막 코팅", "permacoat", 7),
    ("퍼마코트 사용 후기", "permacoat", 7),
    ("가구코팅 추천", "livingcoat", 7),
    ("나눔랩 코팅제", "coating_a", 7),
    ("유리막코팅제", "coating_a", 7),
    ("나눔랩 세정제", "cleaner", 7),
    ("자동차코팅제", "permacoat", 9),
    ("리빙코트", "livingcoat", 9),
    ("세차 관리제", "cleaner", 9),
    ("나눔랩 코팅제", "coating_c", 7),
    ("자동차 유리막코팅", "coating_c", 9),
    ("나눔랩 코팅제", "coating_d", 7),
    ("셀프 유리막코팅제", "coating_d", 9),
    ("나눔랩 코팅제", "coating_b", 7),
    ("유리막코팅제", "coating_b", 7),
    ("나눔랩 코팅제", "coating_general", 7),
    ("차량용 유리막코팅", "coating_general", 9),
    ("리빙코트 처음 사용법", "livingcoat", 9),
    ("리빙코트 원목", "livingcoat", 9),
    ("나무 가구 실내코팅", "livingcoat", 9),
    ("가구 리빙코트 방법", "livingcoat", 9),
    ("가구코팅 가성비", "livingcoat", 9),
    ("원목 리빙코트", "livingcoat", 9),
    ("가구코팅 광택", "livingcoat", 9),
    ("실내코팅 비추천 이유", "livingcoat", 9),
    ("가구코팅 DIY", "livingcoat", 9),
    ("가구코팅 주방", "livingcoat", 9),
    ("가구코팅 가격 비교", "livingcoat", 9),
    ("욕실 가구코팅", "livingcoat", 9),
    ("실내코팅 원목", "livingcoat", 9),
    ("가구코팅 욕실", "livingcoat", 9),
    ("셀프 퍼마코트 순서", "permacoat", 9),
    ("신차 자동차코팅제", "permacoat", 9),
    ("유리막코팅 지속 기간", "permacoat", 9),
    ("퍼마코트 가격 비교", "permacoat", 9),
    ("퍼마코트 직접 해봤어요", "permacoat", 9),
    ("자동차코팅제 직접", "permacoat", 9),
    ("중고차 퍼마코트", "permacoat", 9),
    ("쉬운 자동차코팅제", "permacoat", 9),
    ("쉬운 자동차 코팅제 추천", "permacoat", 9),
    ("유리막코팅 가격 비교", "permacoat", 9),
    ("효과 자동차 코팅제 추천", "permacoat", 9),
    ("자동차코팅제 직접 해봤어요", "permacoat", 9),
    ("유리막코팅 가성비", "permacoat", 9),
    ("자동차코팅제 가성비", "permacoat", 9),
    ("신차 자동차코팅제", "coating_general", 9),
    ("중고차 차량코팅제", "coating_general", 9),
    ("셀프 차 코팅", "coating_general", 9),
    ("쉬운 차량코팅제", "coating_general", 9),
    ("유리막코팅제 가격 비교", "coating_general", 9),
    ("자동차코팅제 직접", "coating_general", 9),
    ("차량코팅제 직접", "coating_general", 9),
    ("쉬운 자동차코팅제", "coating_general", 9),
    ("신차 차 코팅", "coating_general", 9),
    ("후기 유리막코팅제", "coating_general", 9),
    ("차량코팅제 어떤게 좋아요", "coating_general", 9),
    ("유리막코팅제 브랜드 비교", "coating_general", 9),
    ("자동차코팅제 직접 해봤어요", "coating_general", 9),
    ("자동차코팅제 효과 좋은", "coating_general", 9),
    ("유리막코팅제 장마철", "coating_general", 9),
]

keyword_tasks = []
seen = set()
for kw, pk, pri in TASKS_RAW:
    key = (kw, pk)
    if key in seen:
        continue
    seen.add(key)
    keyword_tasks.append(
        {
            "keyword": kw,
            "product_key": pk,
            "product_url": PRODUCTS[pk],
            "mode": "boost",
            "priority": pri,
        }
    )

cfg = {
    "products": PRODUCTS,
    "target_urls": list(dict.fromkeys(PRODUCTS.values())),
    "keywords": sorted({t["keyword"] for t in keyword_tasks}),
    "keyword_tasks": keyword_tasks,
    "boost_sessions": 3,
    "maintain_sessions": 1,
    "max_pages": 10,
    "stay_time_range": [45, 90],
}

Path("traffic_config.json").write_text(
    json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Wrote {len(keyword_tasks)} keyword_tasks to traffic_config.json")
