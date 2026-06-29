# -*- coding: utf-8 -*-
"""
API 기반 네이버 쇼핑 순위 조회 (403·봇차단 우회, Cloudtype 24h용).

우선순위:
  1. NAVER_CLIENT_ID + NAVER_CLIENT_SECRET — 네이버 쇼핑 검색 API (최대 1000위, 권장)
  2. SERPAPI_KEY — Naver 쇼핑 캐러셀 (~8위, 보조)
  3. GOOGLE_API_KEY + GOOGLE_CSE_ID — 폴백
"""
from __future__ import annotations

import os
import re
import time
from typing import Callable

import requests

from env_loader import load_env

SERPAPI_URL = "https://serpapi.com/search.json"
CSE_URL = "https://www.googleapis.com/customsearch/v1"
NAVER_SHOP_URL = "https://openapi.naver.com/v1/search/shop.json"
DEFAULT_MAX_PAGES = 20
NAVER_MAX_ITEMS = 1000


def _pid_from_link(link: str) -> str | None:
    m = re.search(r"/products/(\d+)", link or "")
    return m.group(1) if m else None


def _should_use_api() -> bool:
    load_env()
    mode = os.environ.get("RANK_USE_API", "auto").strip().lower()
    has_key = bool(
        os.environ.get("NAVER_CLIENT_ID")
        or os.environ.get("SERPAPI_KEY")
        or (os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID"))
    )
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on"):
        return has_key
    return has_key


def check_product_rank_naver_open(
    keyword: str,
    product_id: str,
    *,
    max_items: int = NAVER_MAX_ITEMS,
    logger: Callable[[str], None] | None = None,
) -> int | None:
    """네이버 쇼핑 검색 Open API — 최대 1000위."""
    cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
    secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        return None

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    keyword = keyword.strip()
    headers = {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}
    cumulative = 0
    log(f"🔑 [Naver API] '{keyword}' 상품 {product_id} (최대 {max_items}위)")

    for start in range(1, min(max_items, NAVER_MAX_ITEMS) + 1, 100):
        try:
            res = requests.get(
                NAVER_SHOP_URL,
                headers=headers,
                params={"query": keyword, "display": 100, "start": start},
                timeout=20,
            )
            if res.status_code == 429:
                log("   ⚠️ Naver API 429 — 잠시 후 재시도")
                time.sleep(3)
                res = requests.get(
                    NAVER_SHOP_URL,
                    headers=headers,
                    params={"query": keyword, "display": 100, "start": start},
                    timeout=20,
                )
            if res.status_code != 200:
                log(f"   ⚠️ Naver API HTTP {res.status_code}")
                break
            payload = res.json()
            items = payload.get("items") or []
        except Exception as exc:
            log(f"   ⚠️ Naver API 오류: {exc}")
            break

        if not items:
            log(f"   start={start} 결과 없음 — 종료")
            break

        for item in items:
            cumulative += 1
            link = item.get("link") or ""
            if product_id in link or _pid_from_link(link) == product_id:
                log(f"✅ [Naver API] {product_id}: {cumulative}위")
                return cumulative

        if len(items) < 100:
            break
        time.sleep(float(os.environ.get("NAVER_API_DELAY_SEC", "0.3")))

    log(f"⚠️ [Naver API] {product_id} {cumulative}위 이후 미발견")
    return None


def check_product_rank_serpapi(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    logger: Callable[[str], None] | None = None,
) -> int | None:
    """SerpAPI Naver 쇼핑 캐러셀 (~8건, 보조)."""
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        return None

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    keyword = keyword.strip()
    cumulative = 0
    log(f"🔑 [SerpAPI] '{keyword}' 상품 {product_id} (캐러셀)")

    for page in range(1, max_pages + 1):
        params = {
            "engine": "naver",
            "query": keyword,
            "api_key": api_key,
            "page": page,
        }
        try:
            res = requests.get(SERPAPI_URL, params=params, timeout=30)
            if res.status_code != 200:
                log(f"   ⚠️ SerpAPI HTTP {res.status_code}")
                break
            data = res.json()
            if data.get("error"):
                log(f"   ⚠️ SerpAPI: {data['error']}")
                break
        except Exception as exc:
            log(f"   ⚠️ SerpAPI 오류: {exc}")
            break

        items = data.get("shopping_results") or []
        if not items:
            break

        for item in items:
            cumulative += 1
            link = item.get("link") or item.get("product_link") or ""
            pid = _pid_from_link(link)
            if pid == product_id:
                log(f"✅ [SerpAPI] {product_id}: {cumulative}위 (캐러셀)")
                return cumulative

        if page < max_pages:
            time.sleep(float(os.environ.get("SERPAPI_DELAY_SEC", "1.2")))

    return None


def check_product_rank_google_cse(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = 10,
    logger: Callable[[str], None] | None = None,
) -> int | None:
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = os.environ.get("GOOGLE_CSE_ID", "").strip()
    if not api_key or not cx:
        return None

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    q = f"{keyword} site:smartstore.naver.com"
    log(f"🔑 [Google CSE] '{keyword}' 상품 {product_id}")

    cumulative = 0
    for page in range(max_pages):
        start = page * 10 + 1
        try:
            res = requests.get(
                CSE_URL,
                params={"key": api_key, "cx": cx, "q": q, "start": start, "num": 10},
                timeout=20,
            )
            res.raise_for_status()
            items = res.json().get("items") or []
        except Exception as exc:
            log(f"   ⚠️ CSE 오류: {exc}")
            break

        if not items:
            break

        for item in items:
            cumulative += 1
            link = item.get("link", "")
            if product_id in link:
                log(f"✅ [CSE] {product_id}: {cumulative}위")
                return cumulative

        time.sleep(0.5)

    return None


def check_product_rank_api(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    logger: Callable[[str], None] | None = None,
) -> int | None:
    """Naver Open API → SerpAPI → Google CSE."""
    load_env()
    if not _should_use_api():
        return None

    max_items = min(NAVER_MAX_ITEMS, max_pages * 40)

    rank = check_product_rank_naver_open(
        keyword, product_id, max_items=max_items, logger=logger
    )
    if rank is not None:
        return rank

    rank = check_product_rank_serpapi(
        keyword, product_id, max_pages=max_pages, logger=logger
    )
    if rank is not None:
        return rank

    return check_product_rank_google_cse(
        keyword, product_id, max_pages=min(10, max_pages), logger=logger
    )
