"""
네이버 모바일 검색 순위 체커 (stealth 적용)

- playwright-stealth로 봇 탐지 우회
- Galaxy S9+ 모바일 에뮬레이션
- 스마트스토어 상품 블록 기반 순위 계산
"""

import asyncio
import random
from playwright.async_api import async_playwright

# playwright-stealth 임포트 (없으면 경고만 출력)
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    print("[경고] playwright-stealth 미설치. 봇 탐지 위험 있음.")
    print("       설치: pip install playwright-stealth")


async def check_naver_rank(keyword: str, target_url: str, max_scrolls: int = 5) -> int:
    """
    네이버 모바일 검색에서 target_url의 순위를 반환합니다.

    Args:
        keyword: 검색 키워드 (예: "나노코팅")
        target_url: 찾을 스토어 URL 일부 (예: "smartstore.naver.com/nanumlab")
        max_scrolls: 최대 스크롤 횟수 (페이지 추가 로드)

    Returns:
        순위 (1부터 시작). 미발견 시 -1 반환.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # True로 변경 시 headless 모드
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        device = p.devices["Galaxy S9+"]
        context_args = {k: v for k, v in device.items() if k != "default_browser_type"}

        context = await browser.new_context(
            **context_args,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )

        page = await context.new_page()

        # ── stealth 적용 (핵심: navigator.webdriver 숨김 등) ──
        if STEALTH_AVAILABLE:
            await stealth_async(page)
            print("[stealth] 봇 탐지 우회 적용 완료")

        search_url = f"https://m.search.naver.com/search.naver?query={keyword}&where=m_blog"
        # 쇼핑 검색으로 변경하려면:
        # search_url = f"https://m.search.naver.com/search.naver?query={keyword}&where=m_shop"

        print(f"[검색] 키워드: {keyword}")
        print(f"[URL] {search_url}")

        await page.goto(search_url, wait_until="networkidle")
        await asyncio.sleep(random.uniform(1.5, 3.0))  # 사람처럼 랜덤 대기

        rank = -1
        found = False
        item_counter = 0  # 발견된 결과 아이템 순서 카운터

        for scroll_idx in range(max_scrolls):
            print(f"[스크롤 {scroll_idx + 1}/{max_scrolls}] 링크 탐색 중...")

            # 네이버 검색 결과 상품/스토어 블록 셀렉터
            # 실제 DOM에 따라 조정 필요
            result_items = await page.query_selector_all(
                "a[href*='smartstore.naver.com'], "
                "a[href*='shopping.naver.com'], "
                "a[href*='m.shopping.naver.com']"
            )

            for link in result_items:
                href = await link.get_attribute("href")
                if not href:
                    continue

                item_counter += 1

                if target_url.lower() in href.lower():
                    rank = item_counter
                    found = True
                    print(f"[발견!] 순위: {rank}위 | URL: {href}")
                    break

            if found:
                break

            # 추가 결과 로드를 위한 스크롤
            await page.mouse.wheel(0, 2500)
            await asyncio.sleep(random.uniform(1.5, 2.5))

        await browser.close()

        if not found:
            print(f"[미발견] '{target_url}' 이 검색 결과 내에 없습니다.")

        return rank


async def run_bulk_check(keywords: list[str], target_url: str) -> dict[str, int]:
    """여러 키워드에 대해 순위를 순차적으로 체크합니다."""
    results = {}
    for kw in keywords:
        print(f"\n{'='*50}")
        rank = await check_naver_rank(kw, target_url)
        results[kw] = rank
        # 키워드 간 랜덤 대기 (봇 탐지 방지)
        wait = random.uniform(3.0, 6.0)
        print(f"[대기] 다음 키워드까지 {wait:.1f}초 대기...")
        await asyncio.sleep(wait)

    return results


if __name__ == "__main__":
    # ── 설정 ──────────────────────────────────────────
    TARGET_STORE = "smartstore.naver.com/nanumlab"
    KEYWORDS = [
        "나노코팅",
        # 추가 키워드를 여기에 입력하세요
    ]
    # ─────────────────────────────────────────────────

    async def main():
        if len(KEYWORDS) == 1:
            rank = await check_naver_rank(KEYWORDS[0], TARGET_STORE)
            print(f"\n[결과] '{KEYWORDS[0]}' → {rank}위" if rank > 0 else f"\n[결과] '{KEYWORDS[0]}' → 미노출")
        else:
            results = await run_bulk_check(KEYWORDS, TARGET_STORE)
            print("\n" + "=" * 50)
            print("[최종 결과]")
            for kw, r in results.items():
                print(f"  {kw}: {r}위" if r > 0 else f"  {kw}: 미노출")

    asyncio.run(main())
