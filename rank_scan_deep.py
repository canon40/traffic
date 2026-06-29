# -*- coding: utf-8 -*-
"""Playwright 딥 순위 스캔 — API 우선, 스텔스·쿠키·Captcha 대기."""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Callable

from rank_tracker import MOBILE_UA, _extract_ordered_product_ids, _shopping_search_url

try:
    from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

    _PW_OK = True
except ImportError:
    _PW_OK = False
    Browser = BrowserContext = Page = Playwright = None  # type: ignore

try:
    from playwright_stealth import Stealth

    def _apply_stealth(page: Page) -> None:
        Stealth().apply_stealth_sync(page)
except ImportError:
    try:
        from playwright_stealth import stealth_sync as _stealth_legacy

        def _apply_stealth(page: Page) -> None:
            _stealth_legacy(page)
    except ImportError:
        def _apply_stealth(page: Page) -> None:
            pass

DEFAULT_DEEP_PAGES = 20
ITEMS_PER_PAGE = 40
NAVER_API_MAX_PAGES = 25
COOKIE_FILE = Path(__file__).resolve().parent / "data" / "naver_rank_cookies.json"
MANUAL_CAPTCHA_WAIT_SEC = int(os.environ.get("RANK_CAPTCHA_WAIT_SEC", "180"))

_DEVICE_NAMES = ("Galaxy S9+", "Pixel 5", "iPhone 13 Pro", "iPhone 12")


def playwright_available() -> bool:
    return _PW_OK


def _headless_default() -> bool:
    return os.environ.get("RANK_DEEP_HEADLESS", "1").strip().lower() not in ("0", "false", "no")


def _skip_playwright() -> bool:
    return os.environ.get("RANK_DEEP_SKIP_PW", "0").strip().lower() in ("1", "true", "yes")


def _log(logger: Callable[[str], None] | None, msg: str) -> None:
    if logger:
        logger(msg)


def is_blocked_page(page: Page | None, html: str) -> bool:
    """URL·본문·상품 링크 수로 차단 판별 (captcha 단독 문자열 오탐 방지)."""
    if not html or len(html) < 400:
        return True
    if page is not None:
        try:
            url = (page.url or "").lower()
            if any(x in url for x in ("captcha", "security_check", "blocked", "nidlogin")):
                return True
        except Exception:
            pass
        try:
            product_links = page.locator(
                'a[href*="/products/"], a[href*="smartstore"]'
            ).count()
        except Exception:
            product_links = 0
    else:
        product_links = html.lower().count("/products/")

    if product_links >= 5:
        strong = (
            "비정상적인 접근",
            "자동입력 방지",
            "보안 확인을",
            "access denied",
            "unusual traffic",
            "자동등록방지",
        )
        low = html.lower()
        return any(m in html for m in strong) or "recaptcha" in low

    low = html.lower()
    markers = (
        "비정상적인",
        "자동입력",
        "자동등록방지",
        "recaptcha",
        "security_check",
        "access denied",
        "unusual traffic",
        "보안 확인",
    )
    return any(m in low for m in markers)


def is_blocked_html(html: str) -> bool:
    return is_blocked_page(None, html)


def _human_pause(lo: float = 1.2, hi: float = 2.8) -> None:
    time.sleep(random.uniform(lo, hi))


def _human_scroll(page: Page) -> None:
    for _ in range(random.randint(2, 4)):
        page.mouse.wheel(0, random.randint(400, 900))
        _human_pause(0.4, 0.9)


def _load_cookies(context: BrowserContext) -> bool:
    if not COOKIE_FILE.is_file():
        return False
    try:
        raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        cookies = raw if isinstance(raw, list) else raw.get("cookies") or []
        if cookies:
            context.add_cookies(cookies)
            return True
    except Exception:
        pass
    return False


def _save_cookies(context: BrowserContext) -> None:
    try:
        cookies = context.cookies()
        if not cookies:
            return
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _api_rank_first(
    keyword: str,
    product_id: str,
    *,
    max_pages: int,
    logger: Callable[[str], None] | None,
) -> tuple[int | None, bool]:
    """(순위, API로 요청 범위 스캔 완료 여부). API 미설정 시 (None, False)."""
    try:
        from rank_api_provider import _should_use_api, check_product_rank_api

        if not _should_use_api():
            return None, False
        rank = check_product_rank_api(
            keyword,
            product_id,
            max_pages=min(max_pages, NAVER_API_MAX_PAGES),
            logger=logger,
        )
        return (rank, True) if rank is not None else (None, True)
    except Exception as exc:
        _log(logger, f"   ℹ️ API 순위 스킵: {exc}")
        return None, False


def _playwright_start_page(max_pages: int, api_done: bool) -> tuple[int, int]:
    """Playwright 시작 페이지·누적 순위 오프셋."""
    if api_done:
        if max_pages <= NAVER_API_MAX_PAGES:
            return 0, 0
        return NAVER_API_MAX_PAGES + 1, NAVER_API_MAX_PAGES * ITEMS_PER_PAGE
    return 1, 0


def _goto_search_page(
    page: Page,
    keyword: str,
    start: int,
    *,
    logger: Callable[[str], None] | None,
    headless: bool = True,
    retries: int = 2,
) -> str | None:
    url = _shopping_search_url(keyword, start=start)
    referer = "https://m.naver.com/"
    for attempt in range(retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35_000, referer=referer)
            _human_pause(1.5, 3.0)
            _human_scroll(page)
            try:
                page.wait_for_selector(
                    'a[href*="/products/"], a[href*="smartstore"]',
                    timeout=10_000,
                )
            except Exception:
                pass
            html = page.content()
        except Exception as exc:
            _log(logger, f"   ⚠️ 페이지 로드 실패 — {exc}")
            html = ""

        if html and not is_blocked_page(page, html):
            return html

        if not headless and html and is_blocked_page(page, html):
            _log(logger, f"   ⏸️ 캡차/보안 페이지 — 브라우저에서 풀어주세요 (최대 {MANUAL_CAPTCHA_WAIT_SEC}초)")
            deadline = time.time() + MANUAL_CAPTCHA_WAIT_SEC
            while time.time() < deadline:
                time.sleep(3)
                try:
                    html = page.content()
                    if html and not is_blocked_page(page, html):
                        return html
                except Exception:
                    pass
            _log(logger, "   ⚠️ 수동 캡차 대기 시간 초과")

        if attempt < retries:
            wait = random.uniform(40, 75) * (attempt + 1)
            _log(logger, f"   ⏳ 봇 감지 — {wait:.0f}초 대기 후 재시도 ({attempt + 1}/{retries})")
            time.sleep(wait)
            try:
                page.goto("https://m.naver.com/", wait_until="domcontentloaded", timeout=20_000)
                _human_pause(2.0, 4.0)
            except Exception:
                pass
    _log(logger, "   ⚠️ 봇 차단 지속 — 이 키워드 Playwright 중단")
    return None


class DeepRankBrowser:
    """키워드 간 브라우저·쿠키 재사용 (병렬 1 권장). Playwright는 필요할 때만 기동."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        logger: Callable[[str], None] | None = None,
    ):
        self.headless = _headless_default() if headless is None else headless
        self.logger = logger
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._started = False
        self._block_streak = 0

    def __enter__(self) -> DeepRankBrowser:
        return self

    def _ensure_browser(self) -> bool:
        if self._page is not None:
            return True
        if not _PW_OK:
            raise RuntimeError("playwright 미설치 — install_playwright.bat 실행")
        self._pw = sync_playwright().start()
        device_name = random.choice(_DEVICE_NAMES)
        device = self._pw.devices.get(device_name) or self._pw.devices["Pixel 5"]
        ctx_args = {k: v for k, v in device.items() if k != "default_browser_type"}
        ctx_args.pop("user_agent", None)
        ctx_args["user_agent"] = MOBILE_UA
        ctx_args["locale"] = "ko-KR"
        ctx_args["timezone_id"] = "Asia/Seoul"
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(**ctx_args)
        _load_cookies(self._context)
        self._page = self._context.new_page()
        _apply_stealth(self._page)
        self._warmup()
        self._started = True
        _log(self.logger, f"🌐 딥스캔 브라우저 시작 ({device_name}, headless={self.headless})")
        return True

    def _warmup(self) -> None:
        assert self._page is not None
        try:
            self._page.goto("https://m.naver.com/", wait_until="domcontentloaded", timeout=25_000)
            _human_pause(2.0, 3.5)
            self._page.goto(
                "https://m.search.naver.com/search.naver?query=나눔랩&where=m_shop",
                wait_until="domcontentloaded",
                timeout=25_000,
                referer="https://m.naver.com/",
            )
            _human_pause(1.5, 2.5)
            _human_scroll(self._page)
        except Exception:
            pass

    def between_keywords(self) -> None:
        """키워드 사이 휴식 — 봇 패턴 완화."""
        if not self._page:
            return
        _human_pause(8.0, 14.0)
        try:
            self._page.goto("https://m.naver.com/", wait_until="domcontentloaded", timeout=20_000)
            _human_pause(1.5, 3.0)
        except Exception:
            pass

    def check_rank(
        self,
        keyword: str,
        product_id: str,
        *,
        max_pages: int = DEFAULT_DEEP_PAGES,
    ) -> int | None:
        product_id = str(product_id).strip()
        keyword = keyword.strip()
        _log(
            self.logger,
            f"🔍 [deep] '{keyword}' 상품 {product_id} (최대 {max_pages}페이지 ≒{max_pages * ITEMS_PER_PAGE}위)",
        )

        api_rank, api_done = _api_rank_first(
            keyword, product_id, max_pages=max_pages, logger=self.logger
        )
        if api_rank is not None:
            _log(self.logger, f"✅ [API] 상품 {product_id}: {api_rank}위")
            return api_rank

        start_page, rank_offset = _playwright_start_page(max_pages, api_done)
        if start_page == 0 or _skip_playwright():
            if api_done:
                cap = min(max_pages, NAVER_API_MAX_PAGES) * ITEMS_PER_PAGE
                _log(self.logger, f"⚠️ API {cap}위 내 미발견 — Playwright 생략 (중복·봇 회피)")
            return None

        if self._block_streak >= 2:
            _log(self.logger, "⚠️ 연속 봇 차단 — 남은 키워드는 API만 사용")
            return None

        if not _PW_OK:
            return None

        self._ensure_browser()
        assert self._page is not None

        cumulative = rank_offset
        blocked_this_keyword = False

        for page_num in range(start_page, max_pages + 1):
            start = (page_num - 1) * ITEMS_PER_PAGE + 1
            _log(self.logger, f"   📄 {page_num}페이지 (start={start})")

            html = _goto_search_page(
                self._page,
                keyword,
                start,
                logger=self.logger,
                headless=self.headless,
                retries=2,
            )
            if not html:
                blocked_this_keyword = True
                break

            page_ids = _extract_ordered_product_ids(html)
            try:
                dom_ids = self._page.evaluate(
                    """() => {
                    const links = Array.from(document.querySelectorAll(
                        'a[href*="/products/"], a[href*="smartstore.naver.com"]'
                    ));
                    const seen = new Set(), out = [];
                    for (const a of links) {
                        const m = (a.href || '').match(/\\/products\\/(\\d+)/);
                        if (m && !seen.has(m[1])) { seen.add(m[1]); out.push(m[1]); }
                    }
                    return out;
                }"""
                )
                if dom_ids:
                    page_ids = dom_ids
            except Exception:
                pass

            if not page_ids:
                _log(self.logger, f"   ⚠️ {page_num}페이지 결과 없음 — 탐색 종료")
                break

            for pid in page_ids:
                cumulative += 1
                if pid == product_id:
                    self._block_streak = 0
                    _log(self.logger, f"✅ 상품 {product_id}: {cumulative}위 ({page_num}페이지)")
                    return cumulative

            if page_num < max_pages:
                _human_pause(2.0, 4.5)

        if blocked_this_keyword:
            self._block_streak += 1
        _log(self.logger, f"⚠️ 상품 {product_id} {cumulative}위 이후 미발견 (Playwright)")
        return None

    def __exit__(self, *args) -> None:
        if self._context:
            _save_cookies(self._context)
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._pw = None


def check_product_rank_deep(
    keyword: str,
    product_id: str,
    *,
    max_pages: int = DEFAULT_DEEP_PAGES,
    logger: Callable[[str], None] | None = None,
    headless: bool | None = None,
    session: DeepRankBrowser | None = None,
) -> int | None:
    """
    API(1000위) → Playwright 딥스캔.
    session을 넘기면 브라우저 재사용(권장). 없으면 키워드마다 새 브라우저.
    """
    if session is not None:
        return session.check_rank(keyword, product_id, max_pages=max_pages)

    with DeepRankBrowser(headless=headless, logger=logger) as browser:
        return browser.check_rank(keyword, product_id, max_pages=max_pages)
