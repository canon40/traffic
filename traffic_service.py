"""
traffic_service.py
??????????????????
??? ? ?? ??? ?? Human-like Simulation ???.

?? ??:
  1. Stealth  : playwright-stealth ? navigator.webdriver ??
  2. Warm-up  : ??? ??? ?? ?? ? ????? ??
  3. Jitter   : ???? ?? ??, ??? ??? ???
  4. Journey  : ??? ??? ?? ?? ? ????? ?? ??
  5. Cookie   : storage_state ??/??? ? ? ?? ?? ??
  6. State Machine: ?? ?? ?? ?? (?? Loop ??)

???:
  python traffic_service.py              # traffic_config.json ?? ??
  python traffic_service.py --headless   # headless ??
  python traffic_service.py --reset-cookies  # ??? ?? ?? ? ???
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import sys
import time
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

from playwright.sync_api import Page, sync_playwright

# ?? playwright-stealth (??? ???) ?????????????????????????????????????
try:
    from playwright_stealth import stealth_sync
    _STEALTH_OK = True
except ImportError:
    _STEALTH_OK = False


# ????????????????????????????????????????????????????????????????????
# ?  SAFETY SWITCH  (? ?? ?? ?? ???)                        ?
# ????????????????????????????????????????????????????????????????????

class DetectionAlert(Exception):
    """? ?? ?? ?? ? ?? ??? ???? ?? ??."""


class SafetyObserver:
    """
    ??? ???DOM? ??? ???? ???.

    ?? ??:
      - page.on('response', ...) ? ?? HTTP ?? ??
      - 403 / 429 ?? ? ?? ??? set
      - check(page) ?? ? ??? ?? + CAPTCHA DOM ??
      - ?? ?? ? DetectionAlert ? raise ? ?? ?? ??

    NOTE: ??? ??? ??? ?? ??? ???
          Playwright ??? ??? ????? ? ????
          flag ?? ?? raise ?? ??.
    """

    # ??? CAPTCHA / ?? ??? ??? ??
    CAPTCHA_SELECTORS: list[str] = [
        "div#captcha",
        ".captcha_area",
        "#robot_check",
        "div[class*='captcha']",
        "form[action*='captcha']",
    ]

    def __init__(self) -> None:
        self._blocked: bool = False
        self._block_reason: str = ""

  _IGNORE_429_IN_URL = (
        ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".woff", ".svg",
        "analytics", "tracking", "pixel", "beacon",
    )

    def setup(self, page) -> None:
        """응답 후킹 — 스마트스토어 본문 429만 차단 처리."""
        def _on_response(response) -> None:
            if response.status not in (403, 429):
                return
            url = (response.url or "").lower()
            if any(ext in url for ext in self._IGNORE_429_IN_URL):
                return
            if "smartstore.naver.com" not in url and "shopping.naver.com" not in url:
                return
            rtype = getattr(response.request, "resource_type", "")
            if rtype and rtype not in ("document", "xhr", "fetch"):
                return
            self._blocked = True
            self._block_reason = f"HTTP {response.status} from {response.url[:80]}"

        page.on("response", _on_response)

    def check(self, page) -> None:
        """
        ?? ??? ????? ?????.
        ?? ?? ???? ?????.
        DetectionAlert ? raise ?? ??? ?? ???? ???.
        """
        # 1) HTTP ?? ???
        if self._blocked:
            raise DetectionAlert(self._block_reason)

        # 2) DOM ?? CAPTCHA ??
        for sel in self.CAPTCHA_SELECTORS:
            try:
                if page.query_selector(sel):
                    raise DetectionAlert(f"CAPTCHA DOM ??: {sel}")
            except DetectionAlert:
                raise
            except Exception:
                pass  # ??? ??? ??

    @property
    def triggered(self) -> bool:
        return self._blocked

# ?? ?? ?? ???????????????????????????????????????????????????????????????
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("traffic_service.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("traffic_service")

# ?? ?? ?? ???????????????????????????????????????????????????????????????
CONFIG_FILE   = Path("traffic_config.json")
COOKIE_FILE   = Path("smartstore_user_data/naver_storage.json")
RESULT_LOG    = Path("traffic_service_result.log")

# ?? ???? ??? URL ? (??? ?? ? ?? ?? ??) ??????????????????
WARMUP_URLS: list[str] = [
    "https://news.naver.com/",
    "https://entertain.naver.com/",
    "https://sports.naver.com/",
    "https://blog.naver.com/",
    "https://cafe.naver.com/",
    "https://map.naver.com/",
]

# ?? ??? ?? ? (???? ?? ?? ? User-Agent ????) ????????????????
# Playwright devices ???? ?? ??? ??
DEVICE_POOL: list[str] = [
    "Galaxy S9+",
    "Galaxy S8",
    "Pixel 5",
    "Pixel 7",
    "iPhone 12",
    "iPhone 13",
    "iPhone 14",
]

# ??? ??? ???? ?? ?? ??? (?? DOM ??? ?? ??)
SERP_ITEM_SELECTORS = [
    # ?????? ?? ??
    "a[href*='smartstore.naver.com']",
    # ??? ?? ?? ??
    "a[href*='shopping.naver.com']",
    "a[href*='m.shopping.naver.com']",
    # ?? ?? ?? ??
    ".product_area a",
    ".shop_area a",
    ".g_nm a",           # ??? ?? ???
    "div[class*='product'] a",
    "div[class*='item'] a",
    "li[class*='product'] a",
    # ??? SERP ?? ??
    ".price_area a",
    "._listItem a",
    "[data-shp-area-id] a",
]


# ????????????????????????????????????????????????????????????????????
# ?  STATE MACHINE                                                   ?
# ????????????????????????????????????????????????????????????????????

class State(Enum):
    WARMUP       = auto()   # ???: ??? ??? ??
    BLOG_SEARCH  = auto()   # ??? ?? ? ?? ? ?? ? ???? (?? ???)
    SEARCH       = auto()   # ?? ??? ??
    SERP_BROWSE  = auto()   # SERP ???? (??? ?? ??)
    TARGET_VISIT = auto()   # ?? ??? ??
    DONE         = auto()   # ??


# ????????????????????????????????????????????????????????????????????
# ?  HUMAN-LIKE PRIMITIVES                                           ?
# ????????????????????????????????????????????????????????????????????

def gauss_sleep(mean: float, sigma: float = 0.4, min_s: float = 0.3) -> None:
    """???? ?? ?? (??? ?? ?? ??)."""
    t = max(min_s, random.gauss(mean, sigma))
    log.debug(f"  [sleep] {t:.2f}s")
    time.sleep(t)


class HumanSimulator:
    """
    ???? ???????? ??????? ?? ???.

    - human_mouse_move : ??? ?? ??+??? ??? ??
    - click_element    : bounding_box() ???? ?? ? ?? (?? .click() ?? ??)
    - random_scroll    : ??? ?? ??? ???
    - random_move      : ?? ? ?? ??? ??
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    def human_mouse_move(self, target_x: float, target_y: float) -> None:
        """??+??? ??? ??? ?? (?? ??? ? ??)."""
        # ?? ??? ?? ??? ????? viewport ? ?? ??? ??
        vp = self.page.viewport_size or {"width": 390, "height": 844}
        curr_x = random.uniform(10, vp["width"] - 10)
        curr_y = random.uniform(10, vp["height"] // 3)

        steps = random.randint(10, 22)
        for i in range(1, steps + 1):
            t = i / steps
            # ??? ?? ??? ??? ???
            ease = t * t * (3 - 2 * t)  # smoothstep
            mx = curr_x + (target_x - curr_x) * ease + random.randint(-6, 6)
            my = curr_y + (target_y - curr_y) * ease + random.randint(-6, 6)
            self.page.mouse.move(mx, my)
            time.sleep(random.uniform(0.008, 0.04))

    def click_element(self, element) -> bool:
        """
        ??? bounding_box ???? ?? ??? ?? ? ??.
        ?? element.click()? ?? ???? ??? ? ??.
        """
        try:
            box = element.bounding_box()
            if not box:
                return False
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            self.human_mouse_move(cx, cy)
            gauss_sleep(0.15, 0.08, min_s=0.05)
            self.page.mouse.click(cx, cy)
            return True
        except Exception as e:
            log.debug(f"[HumanSimulator] click_element ??: {e}")
            return False

    def random_scroll(self, total_distance: int = 3000) -> None:
        """sine ?? ?? ????? ???."""
        segments = random.randint(4, 9)
        weights = [math.sin(math.pi * i / max(segments - 1, 1)) + 0.1 for i in range(segments)]
        weight_sum = sum(weights)
        distances = [int(total_distance * w / weight_sum) for w in weights]
        for dist in distances:
            self.page.mouse.wheel(0, dist)
            gauss_sleep(0.7, 0.3)

    def random_move(self) -> None:
        """?? ? ?? ??? ??."""
        vp = self.page.viewport_size or {"width": 390, "height": 844}
        for _ in range(random.randint(2, 5)):
            x = random.randint(30, vp["width"] - 30)
            y = random.randint(100, vp["height"] - 100)
            self.human_mouse_move(x, y)
            gauss_sleep(0.4, 0.2)


# ?? ?? ?? ?? ?? (Page ?? ???) ????????????????????????????????????

def human_scroll(page: Page, total_distance: int = 3000) -> None:
    HumanSimulator(page).random_scroll(total_distance)


def human_type(page: Page, selector: str, text: str) -> None:
    """???? ?? ??? ??? (??? ??)."""
    page.click(selector)
    gauss_sleep(0.5, 0.2)
    for char in text:
        page.keyboard.type(char, delay=random.randint(60, 180))
        if random.random() < 0.08:
            gauss_sleep(0.3, 0.1, min_s=0.1)


def random_mouse_move(page: Page) -> None:
    HumanSimulator(page).random_move()


def load_cookies(context) -> bool:
    """??? ??? ????? ??. ?? ? True."""
    if not COOKIE_FILE.exists():
        return False
    try:
        raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list) and raw:
            context.add_cookies(raw)
            log.info(f"[??] ?? ?? ({len(raw)}?)")
            return True
    except Exception as e:
        log.warning(f"[??] ?? ??: {e}")
    return False


def save_cookies(context) -> None:
    """?? ????? ??? ??? ?????."""
    COOKIE_FILE.parent.mkdir(exist_ok=True)
    cookies = context.cookies()
    COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"[??] ?? ?? ?? ({len(cookies)}? ??)")


BLOCKED_RESOURCE_PATTERNS: list[str] = [
    # ?? / ?? / ??? ??? ? ???? ?? ??? ?? ??
    "**/doubleclick.net/**",
    "**/google-analytics.com/**",
    "**/googletagmanager.com/**",
    "**/facebook.net/**",
    "**/adservice.google.**",
    "**/pagead/**",
    "**/wcs.naver.com/**",   # ??? ? ?? (? ?????? ??)
]


def block_trackers(page) -> None:
    """
    ???? ????? ???? ?????.

    ??:
      - ??? ?? ?? ?? ? ?? ?? ??? ? ??? ??
      - ?3? ???? ?? ????? ?? ??
    """
    def _route_handler(route, request) -> None:
        for pattern in BLOCKED_RESOURCE_PATTERNS:
            # ?? ??? ??
            import fnmatch
            if fnmatch.fnmatch(request.url, pattern):
                route.abort()
                return
        route.continue_()

    page.route("**/*", _route_handler)
    log.info("[Tracker] ????? ??? ?? ???")


# ????????????????????????????????????????????????????????????????????
# ?  STATE HANDLERS                                                  ?
# ????????????????????????????????????????????????????????????????????

def handle_warmup(page: Page) -> None:
    """[State: WARMUP] ??? ?? ?? ??? ???? ?? ??."""
    visit_count = random.randint(2, 3)
    urls = random.sample(WARMUP_URLS, min(visit_count, len(WARMUP_URLS)))
    log.info(f"[Warmup] {visit_count}? ??? ??")
    for url in urls:
        try:
            log.info(f"  [Warmup] {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            gauss_sleep(random.gauss(3.0, 0.8), min_s=1.5)
            human_scroll(page, total_distance=random.randint(500, 1200))
        except Exception as e:
            log.warning(f"  [Warmup] ??: {e}")
    log.info("[Warmup] ??")


def handle_blog_search(page: Page, keyword: str) -> None:
    """[State: BLOG_SEARCH] ??? ?? ? 1~2? ??? ??."""
    blog_keyword = keyword.split()[0] if keyword.split() else keyword
    blog_url = f"https://m.search.naver.com/search.naver?query={quote_plus(blog_keyword)}&where=m_blog"
    log.info(f"[Blog] ???: '{blog_keyword}'")
    page.goto(blog_url, wait_until="domcontentloaded", timeout=20_000)
    gauss_sleep(random.gauss(3.0, 0.8), min_s=1.5)
    human_scroll(page, total_distance=random.randint(800, 1800))

    sim = HumanSimulator(page)
    blog_links = []
    try:
        elements = page.query_selector_all("a[href*='blog.naver.com'], a[href*='m.blog.naver.com']")
        for el in elements:
            href = el.get_attribute("href")
            if href:
                blog_links.append((el, href))
    except Exception:
        pass

    visit_count = min(random.randint(1, 2), len(blog_links))
    log.info(f"[Blog] ??? ??? {visit_count}? ??")

    for el, href in blog_links[:visit_count]:
        try:
            log.info(f"  [Blog] ??? ??: {href[:60]}...")
            sim.click_element(el)
            page.wait_for_load_state("domcontentloaded", timeout=12_000)
            gauss_sleep(random.gauss(5.0, 1.5), min_s=2.0)
            human_scroll(page, total_distance=random.randint(600, 1400))
            gauss_sleep(random.gauss(3.0, 1.0), min_s=1.0)
            page.go_back(wait_until="domcontentloaded", timeout=10_000)
            gauss_sleep(random.gauss(2.0, 0.6), min_s=1.0)
        except Exception as e:
            log.warning(f"  [Blog] ?? ??: {e}")
            try:
                page.go_back()
            except Exception:
                pass

    log.info("[Blog] ??? ?? ?? ? ?? ???? ??")


def handle_search(page: Page, keyword: str) -> None:
    """[State: SEARCH] ??? ??? ?? ??."""
    log.info(f"[Search] ???: '{keyword}'")
    shop_url = f"https://m.search.naver.com/search.naver?query={quote_plus(keyword)}&where=m_shop"
    log.info(f"[Search] ?? ?? URL: {shop_url}")
    page.goto(shop_url, wait_until="domcontentloaded", timeout=20_000)
    gauss_sleep(random.gauss(2.5, 0.6), min_s=1.5)


def _product_id_from_url(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) >= 3 and parts[-2] == "products":
        return parts[-1]
    return ""


def handle_serp_browse(
    page: Page,
    target_store_id: str,
    target_product_id: str = "",
) -> tuple[bool, Optional[str], Optional[int]]:
    """
    [State: SERP_BROWSE]
    SERP(?? ?? ???)?? ?? ?? ??? ?? ?????.
    target_product_id? ??? ?? ?? URL? ?? ?????.
    반환: (발견여부, URL, SERP내 순위)
    """
    log.info("[SERP] ?? ?? ??? ?? ??")

    gauss_sleep(random.uniform(5, 10), 1.0)
    human_scroll(page, total_distance=random.randint(800, 1800))
    random_mouse_move(page)

    all_links: list[str] = []
    for sel in SERP_ITEM_SELECTORS:
        try:
            elements = page.query_selector_all(sel)
            for el in elements:
                href = el.get_attribute("href")
                if href and href.startswith("http"):
                    all_links.append(href)
        except Exception:
            pass

    all_links = list(dict.fromkeys(all_links))

    store_links = [h for h in all_links if target_store_id.lower() in h.lower()]
    if target_product_id:
        product_links = [h for h in store_links if target_product_id in h]
        target_links = product_links or store_links
    else:
        target_links = store_links

    competitor_links = [h for h in all_links if h not in target_links]

    log.info(
        f"[SERP] ??: {len(all_links)} | ??: {len(target_links)} | ???: {len(competitor_links)}"
        + (f" | ??ID: {target_product_id}" if target_product_id else "")
    )

    sim = HumanSimulator(page)
    skip_competitors = os.environ.get("TRAFFIC_SKIP_COMPETITORS", "").lower() in ("1", "true", "yes")
    if competitor_links and not skip_competitors:
        competitors_to_visit = random.sample(
            competitor_links, min(random.randint(1, 2), len(competitor_links))
        )
        for comp_url in competitors_to_visit:
            log.info(f"  [??? ??] {comp_url[:60]}...")
            try:
                comp_el = page.query_selector(f'a[href*="{comp_url[:50]}"]')
                if comp_el and sim.click_element(comp_el):
                    page.wait_for_load_state("domcontentloaded", timeout=15_000)
                else:
                    page.goto(comp_url, wait_until="domcontentloaded", timeout=15_000)
                gauss_sleep(random.gauss(5.0, 1.5), min_s=2.0)
                human_scroll(page, total_distance=random.randint(600, 1500))
                page.go_back(wait_until="domcontentloaded", timeout=10_000)
                gauss_sleep(random.gauss(2.5, 0.8), min_s=1.0)
            except Exception as e:
                log.warning(f"  [??? ??] ??: {e}")
                try:
                    page.go_back()
                except Exception:
                    pass

    human_scroll(page, total_distance=random.randint(500, 1200))
    gauss_sleep(random.gauss(4.0, 1.2), min_s=1.5)

    if target_links:
        needle = target_product_id or target_store_id
        serp_rank: Optional[int] = None
        for idx, href in enumerate(all_links, 1):
            if needle in href:
                serp_rank = idx
                break
        target_el = page.query_selector(f'a[href*="{needle}"]')
        if target_el:
            sim.click_element(target_el)
        return True, target_links[0], serp_rank
    return False, None, None


def handle_target_visit(page: Page, target_url: str, stay_range: tuple[int, int] = (30, 90)) -> float:
    """
    [State: TARGET_VISIT]
    ?? ?????? ??? ?? ? ??? ?? ??.
    """
    log.info(f"[Target] ??: {target_url[:70]}...")
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=20_000)
    except Exception as e:
        log.warning(f"[Target] ??? ?? ?? ?? (?? ??): {e}")

    gauss_sleep(3.0, 0.8)

    # ?? ?? ?? ???? ??
    stay_sec = random.uniform(*stay_range)
    log.info(f"[Target] ?? ??: {stay_sec:.0f}?")

    elapsed = 0.0
    while elapsed < stay_sec:
        action = random.choices(
            ["scroll", "mouse_move", "pause"],
            weights=[0.5, 0.3, 0.2],
        )[0]

        if action == "scroll":
            dist = random.randint(400, 1200)
            human_scroll(page, total_distance=dist)
            elapsed += random.uniform(2, 4)
        elif action == "mouse_move":
            random_mouse_move(page)
            elapsed += random.uniform(1, 2)
        else:  # pause
            pause = random.gauss(4.0, 1.5)
            gauss_sleep(max(1.0, pause), 0.5)
            elapsed += pause

    log.info("[Target] ?? ??")
    return round(stay_sec, 1)
# ?  MAIN SESSION RUNNER                                             ?
# ????????????????????????????????????????????????????????????????????

def run_session(
    keyword: str,
    target_store_id: str,
    target_urls: list[str],
    headless: bool = False,
    stay_range: tuple[int, int] = (30, 90),
    preferred_url: str = "",
    browser_profile: dict | None = None,
) -> dict:
    """
    ?? ??-?? ??? ?????.
    State Machine: WARMUP ? SEARCH ? SERP_BROWSE ? TARGET_VISIT ? DONE
    """
    target_product_id = _product_id_from_url(preferred_url) if preferred_url else ""
    result = {
        "keyword": keyword,
        "target_store_id": target_store_id,
        "target_product_id": target_product_id,
        "preferred_url": preferred_url,
        "started_at": datetime.now().isoformat(),
        "state_trace": [],
        "target_found": False,
        "target_url_visited": None,
        "serp_rank": None,
        "dwell_seconds": None,
        "error": None,
        "browser_profile": None,
    }

    with sync_playwright() as p:
        if browser_profile:
            from user_agent_pool import context_options, profile_hint

            context_args = context_options(browser_profile)
            result["browser_profile"] = browser_profile.get("label", "custom")
            log.info(f"[Device] UA 로테이션: {profile_hint(browser_profile)}")
        else:
            device_name = random.choice(DEVICE_POOL)
            device = p.devices.get(device_name) or p.devices["Galaxy S9+"]
            context_args = {k: v for k, v in device.items() if k != "default_browser_type"}
            result["browser_profile"] = device_name
            log.info(f"[Device] 기본 풀: {device_name}")

        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            **{k: v for k, v in context_args.items() if k not in ("locale", "timezone_id")},
            locale=context_args.get("locale", "ko-KR"),
            timezone_id=context_args.get("timezone_id", "Asia/Seoul"),
        )

        # ?? ????
        had_cookies = load_cookies(context)

        page = context.new_page()

        # ?? Stealth ?? ??????????????????????????????????????????
        if _STEALTH_OK:
            stealth_sync(page)
            log.info("[Stealth] navigator.webdriver ?? ??")
        else:
            log.warning("[Stealth] playwright-stealth ??? ? pip install playwright-stealth")

        # ?? Safety Observer + Tracker ?? ??? ????????????????
        observer = SafetyObserver()
        observer.setup(page)
        block_trackers(page)

        # ?? ??? WARMUP, ??? BLOG_SEARCH(?? ???)??
        state = State.WARMUP if not had_cookies else State.BLOG_SEARCH
        log.info(f"[Session] ?? ??: {state.name} | ???: '{keyword}'")

        try:
            # ?? State Machine Loop ????????????????????????????????
            while state != State.DONE:
                result["state_trace"].append(state.name)

                if state == State.WARMUP:
                    handle_warmup(page)
                    observer.check(page)          # ? Safety check
                    state = State.BLOG_SEARCH

                elif state == State.BLOG_SEARCH:
                    handle_blog_search(page, keyword)
                    observer.check(page)          # ? Safety check
                    state = State.SEARCH

                elif state == State.SEARCH:
                    handle_search(page, keyword)
                    observer.check(page)          # ? Safety check
                    state = State.SERP_BROWSE

                elif state == State.SERP_BROWSE:
                    found, href, serp_rank = handle_serp_browse(
                        page, target_store_id, target_product_id=target_product_id
                    )
                    observer.check(page)          # ? Safety check
                    result["target_found"] = found
                    result["serp_rank"] = serp_rank

                    if found and href:
                        result["target_url_visited"] = href
                        state = State.TARGET_VISIT
                    else:
                        fallback_url = preferred_url or (random.choice(target_urls) if target_urls else "")
                        if fallback_url:
                            log.info(f"[SERP] fallback URL: {fallback_url[:60]}...")
                            result["target_url_visited"] = fallback_url
                            result["target_found"] = False
                            state = State.TARGET_VISIT
                        else:
                            log.info("[SERP] no target, session end")
                            state = State.DONE

                elif state == State.TARGET_VISIT:
                    visit_url = result["target_url_visited"]
                    if visit_url:
                        result["dwell_seconds"] = handle_target_visit(
                            page, visit_url, stay_range=stay_range
                        )
                    observer.check(page)          # ? Safety check
                    state = State.DONE

        except DetectionAlert as e:
            reason = str(e)
            result["error"] = f"[차단] {reason}"
            result["detected"] = True
            log.warning(f"[Safety] 차단 감지: {reason}")
            if "429" in reason:
                try:
                    from traffic_rate_limit import record_429
                    wait = record_429()
                    log.warning(f"[RateLimit] 429 누적 — {wait}초 쿨다운 등록")
                except Exception:
                    pass
            if COOKIE_FILE.exists():
                COOKIE_FILE.unlink()
                log.info("[Safety] 쿠키 삭제 (세션 초기화)")

        except Exception as e:
            result["error"] = str(e)
            log.error(f"[Session] ??: {e}", exc_info=True)
        finally:
            # ?? ??? ?? ?? (?? ??? ??? ?? ???)
            if not result.get("detected"):
                save_cookies(context)
            browser.close()

    result["finished_at"] = datetime.now().isoformat()
    result["state_trace"].append("DONE")
    if not result.get("detected") and not result.get("error"):
        try:
            from traffic_rate_limit import record_success
            record_success()
        except Exception:
            pass
    return result


# ????????????????????????????????????????????????????????????????????
# ?  CONFIG & ENTRY POINT                                            ?
# ????????????????????????????????????????????????????????????????????

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _resolve_tasks(cfg: dict) -> list[dict]:
    """keyword_tasks ?? keywords ??? ?? ??? ??."""
    products: dict[str, str] = cfg.get("products", {})
    tasks = cfg.get("keyword_tasks")
    if tasks:
        resolved = []
        for t in tasks:
            kw = str(t.get("keyword", "")).strip()
            if not kw:
                continue
            product_key = t.get("product_key", "")
            url = t.get("product_url") or products.get(product_key, "")
            resolved.append(
                {
                    "keyword": kw,
                    "product_url": url,
                    "mode": t.get("mode", "boost"),
                    "priority": int(t.get("priority", 5)),
                }
            )
        return resolved

    target_urls = cfg.get("target_urls", [])
    default_url = target_urls[0] if target_urls else ""
    return [
        {"keyword": kw, "product_url": default_url, "mode": "boost", "priority": 5}
        for kw in cfg.get("keywords", [])
        if str(kw).strip()
    ]


def _sessions_for_task(task: dict, rank: Optional[int], cfg: dict) -> int:
    """Rank-based session count: maintain 1-6, boost if not found."""
    mode = task.get("mode", "boost")
    if rank is not None and 1 <= rank <= 6:
        return int(cfg.get("maintain_sessions", 1))
    if mode == "maintain" and rank is not None and rank > 0:
        return int(cfg.get("maintain_sessions", 1))
    base = int(cfg.get("boost_sessions", 3))
    if task.get("priority", 5) >= 8:
        return base + 1
    return base



def main() -> int:
    parser = argparse.ArgumentParser(description="Naver traffic simulation service")
    parser.add_argument("--headless", action="store_true", help="Headless mode")
    parser.add_argument("--reset-cookies", action="store_true", help="Delete saved cookies")
    parser.add_argument("--keyword", type=str, default=None, help="Single keyword")
    parser.add_argument("--loops", type=int, default=1, help="Loop count (non-campaign)")
    parser.add_argument(
        "--campaign",
        action="store_true",
        help="Run keyword_tasks: boost unranked, maintain top 1-6",
    )
    parser.add_argument("--check-rank", action="store_true", help="Check Naver rank before traffic")
    args = parser.parse_args()

    if args.reset_cookies and COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
        log.info("[cookie] deleted")

    cfg = load_config()
    target_urls: list[str] = cfg.get("target_urls", [])
    stay_range = tuple(cfg.get("stay_time_range", [30, 90]))

    target_store_id = "nanumlab"
    if target_urls:
        parsed = urlparse(target_urls[0])
        parts = parsed.path.strip("/").split("/")
        if parts:
            target_store_id = parts[0]

    tasks = _resolve_tasks(cfg)
    if args.keyword:
        tasks = [t for t in tasks if t["keyword"] == args.keyword] or [
            {"keyword": args.keyword, "product_url": target_urls[0] if target_urls else "", "mode": "boost", "priority": 5}
        ]

    if not tasks:
        log.error("No keywords. Set keyword_tasks or keywords in traffic_config.json")
        return 1

    if args.campaign:
        tasks = sorted(tasks, key=lambda t: (-t.get("priority", 5), t["keyword"]))
        log.info(f"[Campaign] tasks={len(tasks)} store={target_store_id}")
    else:
        log.info(f"[Main] keywords={len(tasks)} store={target_store_id} loops={args.loops}")

    rank_fn = None
    if args.check_rank or args.campaign:
        try:
            from naver_rank import check_naver_rank_sync
            rank_fn = check_naver_rank_sync
        except ImportError:
            log.warning("naver_rank module missing; rank-based scheduling disabled")

    all_results = []
    work_queue: list[tuple[dict, int]] = []

    if args.campaign:
        for task in tasks:
            rank = None
            if rank_fn and task.get("product_url"):
                try:
                    rank = rank_fn(task["keyword"], task["product_url"])
                    log.info(f"[Rank] '{task['keyword']}' -> {rank if rank > 0 else '???'}")
                except Exception as e:
                    log.warning(f"[Rank] check failed: {e}")
            sessions = _sessions_for_task(task, rank, cfg)
            if rank is not None and 1 <= rank <= 6:
                log.info(f"[Campaign] maintain 1~6? ({rank}?): '{task['keyword']}' x{sessions}")
            else:
                log.info(f"[Campaign] boost ???: '{task['keyword']}' x{sessions}")
            for _ in range(sessions):
                work_queue.append((task, sessions))
    else:
        for _ in range(args.loops):
            task = random.choice(tasks)
            work_queue.append((task, 1))

    for loop, (task, _) in enumerate(work_queue):
        kw = task["keyword"]
        preferred = task.get("product_url", "")
        log.info(f"\n{'='*60}")
        log.info(f"[Loop {loop+1}/{len(work_queue)}] keyword='{kw}' product={preferred[-12:] if preferred else '-'}")
        log.info(f"{'='*60}")

        result = run_session(
            keyword=kw,
            target_store_id=target_store_id,
            target_urls=target_urls,
            headless=args.headless,
            stay_range=stay_range,
            preferred_url=preferred,
        )
        all_results.append(result)

        if result.get("detected"):
            status = "DETECTED"
            cooldown = random.uniform(270, 420)
            log.warning(f"[Cooldown] {cooldown:.0f}s")
            time.sleep(cooldown)
        elif result["error"]:
            status = f"ERROR: {result['error']}"
        elif result["target_found"]:
            status = "TARGET_FOUND"
        else:
            status = "FALLBACK"

        log.info(f"[Result] {status} | trace: {' -> '.join(result['state_trace'])}")

        if loop < len(work_queue) - 1 and not result.get("detected"):
            wait = random.gauss(55, 15)
            wait = max(20.0, wait)
            log.info(f"[wait] {wait:.0f}s")
            time.sleep(wait)

    with RESULT_LOG.open("a", encoding="utf-8") as f:
        for r in all_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"\n[done] sessions={len(all_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
