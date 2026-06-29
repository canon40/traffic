# -*- coding: utf-8 -*-
"""
API 기반 네이버 쇼핑 순위 조회 (403·봇차단 우회, Cloudtype 24h용).

환경변수:
  SERPAPI_KEY          — SerpAPI Naver 쇼핑 (권장)
  GOOGLE_API_KEY       — Google Custom Search (폴백)
  GOOGLE_CSE_ID
  RANK_USE_API         — 1|auto|0 (기본 auto: 키 있으면 API 우선)
"""
from __future__ import annotations

import os
import re
import time
from typing import Callable
from urllib.parse import quote

import requests

from env_loader import load_env

SERPAPI_URL = "https://serpapi.com/search.json"
CSE_URL = "https://www.googleapis.com/customsearch/v1"
DEFAULT_MAX_PAGES = 20
ITEMS_PER_PAGE = 10  # SerpAPI Naver 쇼핑 페이지당 약 10건


def _pid_from_link(link: str) -> str | None:
    m = re.search(r"/products/(\d+)", link or "")
    return m.group(1) if m else None


def _should_use_api() -> bool:
    load_env()
    mode = os.environ.get("RANK_USE_API", "auto").strip().lower()
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on"):
        return bool(os.environ.get("SERPAPI_KEY") or os.environ.get("GOOGLE_API_KEY"))
    # auto
    return bool(os.environ.get("SERPAPI_KEY") or (
        os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID")
    ))


def check_product_rank_serpapi(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    logger: Callable[[str], None] | None = None,
) -> int | None:
    api_key = os.environ.get("SERPAPI_KEY", "").strip()
    if not api_key:
        return None

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    keyword = keyword.strip()
    cumulative = 0
    log(f"🔑 [SerpAPI] '{keyword}' 상품 {product_id} (최대 {max_pages}p)")

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
            log(f"   {page}페이지 쇼핑 결과 없음 — 종료")
            break

        for item in items:
            cumulative += 1
            link = item.get("link") or item.get("product_link") or ""
            pid = _pid_from_link(link)
            if pid == product_id:
                log(f"✅ [SerpAPI] {product_id}: {cumulative}위 ({page}페이지)")
                return cumulative

        if page < max_pages:
            time.sleep(float(os.environ.get("SERPAPI_DELAY_SEC", "1.2")))

    log(f"⚠️ [SerpAPI] {product_id} {cumulative}위 이후 미발견")
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
    """SerpAPI → Google CSE 순으로 API 순위 조회."""
    load_env()
    if not _should_use_api():
        return None

    rank = check_product_rank_serpapi(
        keyword, product_id, max_pages=max_pages, logger=logger
    )
    if rank is not None:
        return rank

    return check_product_rank_google_cse(
        keyword, product_id, max_pages=min(10, max_pages), logger=logger
    )
