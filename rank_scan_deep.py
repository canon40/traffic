# -*- coding: utf-8 -*-
"""Playwright 기반 네이버 쇼핑 딥 순위 스캔 (12페이지+ / 403 우회)."""
from __future__ import annotations

import random
import time
from typing import Callable

from rank_tracker import MOBILE_UA, _extract_ordered_product_ids, _shopping_search_url

try:
    from playwright.sync_api import sync_playwright

    _PW_OK = True
except ImportError:
    _PW_OK = False

try:
    from playwright_stealth import stealth_sync

    _STEALTH_OK = True
except ImportError:
    _STEALTH_OK = False

DEFAULT_DEEP_PAGES = 20  # 모바일 40개/페이지 → 최대 800위
ITEMS_PER_PAGE = 40

_EXTRACT_JS = """() => {
    const links = Array.from(document.querySelectorAll(
        'a[href*="/products/"], a[href*="smartstore.naver.com"]'
    ));
    const seen = new Set();
    const ordered = [];
    for (const a of links) {
        const href = a.href || '';
        const m = href.match(/\\/products\\/(\\d+)/);
        if (m && !seen.has(m[1])) {
            seen.add(m[1]);
            ordered.push(m[1]);
        }
    }
    return ordered;
}"""


def _page_product_ids(page, html: str) -> list[str]:
    """DOM JS 추출 우선, HTML regex 폴백."""
    try:
        ids = page.evaluate(_EXTRACT_JS)
        if ids:
            return ids
    except Exception:
        pass
    return _extract_ordered_product_ids(html)


def _check_via_requests(
    keyword: str,
    product_id: str,
    *,
    max_pages: int,
    logger: Callable[[str], None] | None,
) -> int | None:
    """Playwright 실패 시 Referer 포함 HTTP 폴백."""
    import requests

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    headers = {
        "User-Agent": MOBILE_UA,
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.naver.com/",
    }
    pid = str(product_id).strip()
    cumulative = 0

    for page_num in range(1, max_pages + 1):
        start = (page_num - 1) * ITEMS_PER_PAGE + 1
        url = _shopping_search_url(keyword, start=start)
        log(f"   📡 HTTP 폴백 {page_num}페이지 (start={start})")
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 403:
                time.sleep(3)
                res = requests.get(url, headers=headers, timeout=20)
            if res.status_code != 200:
                log(f"   ⚠️ HTTP {res.status_code}")
                break
        except Exception as exc:
            log(f"   ⚠️ HTTP 오류 — {exc}")
            break

        page_ids = _extract_ordered_product_ids(res.text)
        if not page_ids:
            break

        for p in page_ids:
            cumulative += 1
            if p == pid:
                log(f"✅ [HTTP] 상품 {pid}: {cumulative}위")
                return cumulative

        if len(page_ids) < 35:
            break
        time.sleep(random.uniform(0.5, 1.0))

    return None


def check_product_rank_deep(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = DEFAULT_DEEP_PAGES,
    logger: Callable[[str], None] | None = None,
    headless: bool = True,
) -> int | None:
    """
    Playwright + start= 페이징으로 깊은 순위 탐색.
    발견 즉시 반환, 빈 페이지·403 시 중단.
    """
    if not _PW_OK:
        raise RuntimeError("playwright 미설치 — pip install playwright && playwright install chromium")

    def log(msg: str) -> None:
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    keyword = keyword.strip()
    log(f"🔍 [deep] '{keyword}' 상품 {product_id} (최대 {max_pages}페이지 ≒{max_pages * ITEMS_PER_PAGE}위)")

    cumulative_rank = 0

    with sync_playwright() as p:
        device = p.devices.get("Galaxy S9+") or p.devices["Pixel 5"]
        ctx_args = {k: v for k, v in device.items() if k != "default_browser_type"}
        ctx_args["user_agent"] = MOBILE_UA
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(
            **ctx_args,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        page = context.new_page()
        if _STEALTH_OK:
            stealth_sync(page)

        # 네이버 모바일 웜업 (Referer·쿠키 확보)
        try:
            page.goto("https://m.naver.com/", wait_until="domcontentloaded", timeout=20_000)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass

        try:
            for page_num in range(1, max_pages + 1):
                start = (page_num - 1) * ITEMS_PER_PAGE + 1
                url = _shopping_search_url(keyword, start=start)
                log(f"   📄 {page_num}페이지 (start={start})")

                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000, referer="https://m.naver.com/")
                    time.sleep(random.uniform(1.2, 2.0))
                    # 모바일 쇼핑 lazy-load: 짧은 스크롤 후 재수집
                    page.mouse.wheel(0, 800)
                    time.sleep(random.uniform(0.5, 1.0))
                    try:
                        page.wait_for_selector(
                            'a[href*="/products/"], a[href*="smartstore"]',
                            timeout=8_000,
                        )
                    except Exception:
                        pass
                    html = page.content()
                except Exception as exc:
                    log(f"   ⚠️ 페이지 로드 실패 — {exc}")
                    break

                if "captcha" in html.lower() or "비정상적인" in html:
                    log("   ⚠️ 봇 차단(Captcha) 감지 — 중단")
                    break

                page_ids = _page_product_ids(page, html)
                if not page_ids:
                    log(f"   ⚠️ {page_num}페이지 결과 없음 — 탐색 종료")
                    break

                for pid in page_ids:
                    cumulative_rank += 1
                    if pid == product_id:
                        log(f"✅ 상품 {product_id}: {cumulative_rank}위 ({page_num}페이지)")
                        return cumulative_rank

                if page_num < max_pages:
                    time.sleep(random.uniform(0.6, 1.2))

        finally:
            browser.close()

    log(f"⚠️ 상품 {product_id} {cumulative_rank}위 이후 미발견 (Playwright)")
    fallback = _check_via_requests(keyword, product_id, max_pages=max_pages, logger=logger)
    if fallback:
        return fallback
    log(f"⚠️ HTTP 폴백도 미발견")
    return None
