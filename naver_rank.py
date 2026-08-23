"""네이버 모바일 쇼핑 검색 순위 체크 (동기)."""

from __future__ import annotations

import csv
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from stealth_compat import apply_stealth_sync

RANK_LOG = Path("keyword_rank_log.csv")


def _product_id(url: str) -> str:
  parts = url.rstrip("/").split("/")
  return parts[-1] if parts else ""


def check_naver_rank_sync(
    keyword: str,
    target_url: str,
    *,
    max_scrolls: int = 8,
    headless: bool = True,
) -> int:
    """
    네이버 모바일 쇼핑 검색에서 target_url(또는 상품 ID) 순위 반환.
    미발견 시 -1.
    """
    target_needle = _product_id(target_url) or target_url.lower()
    shop_url = f"https://m.search.naver.com/search.naver?query={quote_plus(keyword)}&where=m_shop"

    with sync_playwright() as p:
        device = p.devices.get("Galaxy S9+") or p.devices["Pixel 5"]
        context_args = {k: v for k, v in device.items() if k != "default_browser_type"}
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = browser.new_context(**context_args, locale="ko-KR", timezone_id="Asia/Seoul")
        page = context.new_page()
        apply_stealth_sync(page)

        page.goto(shop_url, wait_until="domcontentloaded", timeout=25_000)
        time.sleep(random.uniform(1.5, 2.5))

        rank = -1
        item_counter = 0
        seen: set[str] = set()

        for _ in range(max_scrolls):
            links = page.query_selector_all(
                "a[href*='smartstore.naver.com'], "
                "a[href*='shopping.naver.com'], "
                "a[href*='m.shopping.naver.com']"
            )
            for link in links:
                href = link.get_attribute("href") or ""
                if not href or href in seen:
                    continue
                seen.add(href)
                item_counter += 1
                if target_needle in href.lower():
                    rank = item_counter
                    break
            if rank > 0:
                break
            page.mouse.wheel(0, 2200)
            time.sleep(random.uniform(1.2, 2.0))

        browser.close()
    return rank


def append_rank_log(keyword: str, target_url: str, rank: int) -> None:
    exists = RANK_LOG.exists()
    with RANK_LOG.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["datetime", "engine", "keyword", "domain", "rank", "url"])
        w.writerow(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "naver_mobile",
                keyword,
                target_url,
                rank if rank > 0 else "N/A",
                "Success" if rank > 0 else "Not Found",
            ]
        )


if __name__ == "__main__":
    import json
    import sys

    cfg_path = Path("traffic_config.json")
    if not cfg_path.exists():
        print("traffic_config.json 없음")
        sys.exit(1)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    tasks = cfg.get("keyword_tasks") or []
    products = cfg.get("products", {})
    for t in tasks[:5]:
        kw = t["keyword"]
        url = t.get("product_url") or products.get(t.get("product_key", ""), "")
        r = check_naver_rank_sync(kw, url)
        print(f"{kw}: {r if r > 0 else '미발견'}")
        append_rank_log(kw, url, r)
        time.sleep(random.uniform(3, 5))
