import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests

CONFIG_PATH = "config.json"
AUDIT_PATH = "seo_audit_history.json"
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

GENERIC_INTROS = (
    "안녕하세요",
    "이번 글에서는",
    "오늘은",
    "정리하면",
    "도움이 되셨길",
)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"product_urls": [], "blog_urls": [], "keywords": []}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _fetch_html(url):
    headers = {"User-Agent": MOBILE_UA}
    res = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    res.raise_for_status()
    return res.text, res.url


def _extract_meta(html, name=None, prop=None):
    if name:
        m = re.search(
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
            html,
            re.I,
        )
        if not m:
            m = re.search(
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(name)}["\']',
                html,
                re.I,
            )
        return m.group(1).strip() if m else ""
    if prop:
        m = re.search(
            rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']*)["\']',
            html,
            re.I,
        )
        if not m:
            m = re.search(
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']{re.escape(prop)}["\']',
                html,
                re.I,
            )
        return m.group(1).strip() if m else ""
    return ""


def _extract_title(html):
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else ""


def _count_tags(html, tag):
    return len(re.findall(rf"<{tag}[^>]*>", html, re.I))


def _images_without_alt(html):
    imgs = re.findall(r"<img[^>]*>", html, re.I)
    missing = 0
    for img in imgs:
        if not re.search(r'alt=["\'][^"\']+["\']', img, re.I):
            missing += 1
    return missing, len(imgs)


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</(p|div|li|h1|h2|h3|tr)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _paragraph_sentence_stats(text: str) -> tuple[int, int]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return 0, 0
    sentence_counts = []
    for paragraph in paragraphs:
        count = len([s for s in re.split(r"(?<=[.!?다요])\s+", paragraph) if s.strip()])
        sentence_counts.append(max(count, 1))
    return max(sentence_counts), len(paragraphs)


def _keyword_repeat_count(text: str, keywords: list[str]) -> tuple[str, int]:
    lowered = text.lower()
    top_kw = ""
    top_count = 0
    for keyword in keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        count = lowered.count(keyword.lower())
        if count > top_count:
            top_kw = keyword
            top_count = count
    return top_kw, top_count


def _extract_h2_like_blocks(html: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.I | re.S)]


def _count_captions(html: str) -> int:
    figcaptions = _count_tags(html, "figcaption")
    caption_blocks = len(re.findall(r'class=["\'][^"\']*caption[^"\']*["\']', html, re.I))
    return figcaptions + caption_blocks


def audit_page(url, page_type="page", target_keywords=None):
    target_keywords = target_keywords or []
    checks = []
    score = 0
    max_score = 0

    def add_check(name, passed, message, weight=1):
        nonlocal score, max_score
        max_score += weight
        if passed:
            score += weight
        checks.append({"name": name, "passed": passed, "message": message, "weight": weight})

    try:
        html, final_url = _fetch_html(url)
    except Exception as e:
        return {
            "url": url,
            "page_type": page_type,
            "success": False,
            "error": str(e),
            "checks": [],
            "score": 0,
            "max_score": 0,
            "grade": "F",
        }

    title = _extract_title(html)
    description = _extract_meta(html, name="description")
    og_title = _extract_meta(html, prop="og:title")
    viewport = _extract_meta(html, name="viewport")
    h1_count = _count_tags(html, "h1")
    missing_alt, img_total = _images_without_alt(html)
    text = _html_to_text(html)

    add_check(
        "페이지 제목(title)",
        bool(title) and 10 <= len(title) <= 70,
        f"{'✓' if title else '✗'} {title[:60] + '…' if len(title) > 60 else (title or '없음')} (권장 10~70자)",
        2,
    )
    add_check(
        "메타 설명(description)",
        bool(description) and 50 <= len(description) <= 160,
        f"{'✓' if description else '✗'} {len(description)}자 (권장 50~160자)",
        2,
    )
    add_check(
        "모바일 viewport",
        "width=device-width" in viewport,
        f"{'✓' if viewport else '✗'} {viewport or 'viewport 미설정'}",
        2,
    )
    add_check(
        "H1 태그",
        h1_count == 1,
        f"{'✓' if h1_count == 1 else '✗'} H1 {h1_count}개 (권장 1개)",
        1,
    )
    add_check(
        "이미지 alt 속성",
        img_total == 0 or missing_alt == 0,
        f"이미지 {img_total}개 중 alt 누락 {missing_alt}개",
        1,
    )
    add_check(
        "OG 태그(공유 미리보기)",
        bool(og_title),
        f"{'✓' if og_title else '✗'} og:title {'있음' if og_title else '없음'}",
        1,
    )

    if target_keywords:
        combined = (title + " " + description + " " + html[:5000]).lower()
        found = [kw for kw in target_keywords if kw.lower() in combined]
        add_check(
            "타겟 키워드 포함",
            len(found) > 0,
            f"발견: {', '.join(found) if found else '없음'} (대상: {', '.join(target_keywords[:3])})",
            2,
        )

    if page_type == "blog":
        max_sentences, paragraph_count = _paragraph_sentence_stats(text)
        add_check(
            "문단 길이",
            paragraph_count > 0 and max_sentences <= 3,
            f"{'✓' if max_sentences <= 3 else '✗'} 최대 {max_sentences}문장 (권장 3문장 이하)",
            2,
        )
        h2_blocks = _extract_h2_like_blocks(html)
        qna_count = sum(1 for block in h2_blocks if "?" in block or "까요" in block or "얼마" in block)
        add_check(
            "Q&A 구조",
            qna_count >= 2,
            f"{'✓' if qna_count >= 2 else '✗'} 질문형 소제목 {qna_count}개 (권장 2개 이상)",
            2,
        )
        table_count = _count_tags(html, "table")
        add_check(
            "표(Table) 구조화",
            table_count >= 1 or "|" in text,
            f"{'✓' if table_count >= 1 or '|' in text else '✗'} 표 {table_count}개",
            2,
        )
        list_count = _count_tags(html, "ul") + _count_tags(html, "ol")
        add_check(
            "리스트 구조화",
            list_count >= 1,
            f"{'✓' if list_count >= 1 else '✗'} 리스트 {list_count}개",
            1,
        )
        caption_count = _count_captions(html)
        add_check(
            "이미지 캡션",
            img_total == 0 or caption_count >= 1,
            f"{'✓' if img_total == 0 or caption_count >= 1 else '✗'} 캡션 {caption_count}개 / 이미지 {img_total}개",
            1,
        )
        internal_links = len(re.findall(r'<a[^>]+href=["\'](?!https?://)[^"\']+["\']', html, re.I))
        add_check(
            "내부 링크 섹션",
            internal_links >= 1 or "함께 보면 좋은 글" in text,
            f"{'✓' if internal_links >= 1 or '함께 보면 좋은 글' in text else '✗'} 내부 링크 {internal_links}개",
            1,
        )
        intro_window = text[:200]
        intro_ok = any(kw.lower() in intro_window.lower() for kw in target_keywords[:2]) if target_keywords else True
        add_check(
            "도입부 두괄식",
            intro_ok and len(intro_window) >= 30,
            f"{'✓' if intro_ok else '✗'} 첫 200자 내 핵심 키워드/요약 확인",
            2,
        )
        keyword_name, keyword_count = _keyword_repeat_count(text, target_keywords)
        add_check(
            "키워드 반복 과다",
            keyword_count <= 5 or not keyword_name,
            f"{'✓' if keyword_count <= 5 or not keyword_name else '✗'} {keyword_name or '키워드'} {keyword_count}회",
            1,
        )
        generic_intro_found = next((intro for intro in GENERIC_INTROS if intro in text[:160]), "")
        add_check(
            "상투적 서론 억제",
            not generic_intro_found,
            f"{'✓' if not generic_intro_found else '✗'} {generic_intro_found or '문제 없음'}",
            1,
        )

    if page_type == "product":
        add_check(
            "HTTPS 보안",
            final_url.startswith("https://"),
            f"{'✓' if final_url.startswith('https') else '✗'} {urlparse(final_url).scheme}",
            1,
        )

    pct = int(score / max_score * 100) if max_score else 0
    if pct >= 80:
        grade = "A"
    elif pct >= 60:
        grade = "B"
    elif pct >= 40:
        grade = "C"
    else:
        grade = "D"

    return {
        "url": url,
        "final_url": final_url,
        "page_type": page_type,
        "success": True,
        "checks": checks,
        "score": score,
        "max_score": max_score,
        "percent": pct,
        "grade": grade,
        "audited_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _product_id_from_url(url: str) -> str:
    try:
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) >= 3 and parts[-2] == "products":
            return parts[-1]
    except Exception:
        pass
    return ""


def _keywords_for_product(config: dict, product_id: str) -> list[str]:
    seo = (config.get("product_seo") or {}).get(product_id, {})
    kws = list(seo.get("keywords") or [])
    if kws:
        return kws
    return [
        k.get("keyword", "")
        for k in config.get("keywords", [])
        if str(k.get("product_id", "")) == product_id and k.get("keyword")
    ][:5]


def _keywords_for_blog(config: dict, blog_url: str) -> list[str]:
    seo = (config.get("blog_seo") or {}).get(blog_url, {})
    return list(seo.get("keywords") or [])


def run_full_audit(logger=None):
    config = load_config()
    default_keywords = [k.get("keyword", "") for k in config.get("keywords", []) if k.get("keyword")]

    results = {"products": [], "blogs": [], "summary": {}}

    for url in config.get("product_urls", []):
        if logger:
            logger(f"🔎 상품 페이지 SEO 점검: {url}")
        pid = _product_id_from_url(url)
        kws = _keywords_for_product(config, pid) or default_keywords[:5]
        results["products"].append(audit_page(url, "product", kws))

    for url in config.get("blog_urls", []):
        if logger:
            logger(f"🔎 블로그 SEO 점검: {url}")
        kws = _keywords_for_blog(config, url) or default_keywords[:5]
        results["blogs"].append(audit_page(url, "blog", kws))

    all_pages = results["products"] + results["blogs"]
    ok_pages = [p for p in all_pages if p.get("success")]
    avg = int(sum(p.get("percent", 0) for p in ok_pages) / len(ok_pages)) if ok_pages else 0
    failed = [p for p in all_pages if not p.get("success")]

    results["summary"] = {
        "total_pages": len(all_pages),
        "audited_ok": len(ok_pages),
        "failed": len(failed),
        "average_score": avg,
        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "recommendations": _build_recommendations(all_pages, config),
    }

    _save_audit_history(results)
    return results


def _build_recommendations(pages, config=None):
    config = config or load_config()
    product_seo = config.get("product_seo") or {}
    blog_seo = config.get("blog_seo") or {}
    recs = []

    for page in pages:
        if not page.get("success"):
            recs.append(f"{page['url']}: 페이지 접근 실패 — URL 확인 필요")
            continue

        url = page.get("url", "")
        failed = {c["name"]: c for c in page.get("checks", []) if not c["passed"]}

        if page.get("page_type") == "product":
            pid = _product_id_from_url(url)
            seo = product_seo.get(pid, {})
            name = seo.get("name") or pid
            if "메타 설명(description)" in failed:
                meta = (seo.get("meta_description") or "").strip()
                if meta:
                    recs.append(
                        f"[product] {name} — 스마트스토어센터 → SEO설정에 메타 설명 붙여넣기: 「{meta}」"
                    )
                else:
                    recs.append(f"[product] {name} — 스마트스토어센터 → SEO설정에 메타 설명 추가 필요")
            for check_name, check in failed.items():
                if check_name == "메타 설명(description)":
                    continue
                recs.append(f"[product] {check_name}: {check['message']}")
            continue

        if page.get("page_type") == "blog":
            seo = blog_seo.get(url, {})
            label = seo.get("label") or url
            if "메타 설명(description)" in failed:
                meta = (seo.get("meta_description") or "").strip()
                if meta:
                    recs.append(
                        f"[blog] {label} — 블로그 설정 → 메타 설명 붙여넣기 ({len(meta)}자): 「{meta}」"
                    )
            if "H1 태그" in failed:
                h1 = seo.get("h1", "")
                if h1:
                    recs.append(
                        f"[blog] {label} — H1을 1개만 사용: 「{h1}」 (초안: blog_drafts/seo_fix_{label}.md)"
                    )
            if "타겟 키워드 포함" in failed:
                kws = seo.get("keywords") or []
                if kws:
                    recs.append(
                        f"[blog] {label} — 본문에 키워드 포함: {', '.join(kws)} (초안 파일 참고)"
                    )
            if "내부 링크 섹션" in failed:
                recs.append(f"[blog] {label} — '함께 보면 좋은 글' 내부 링크 2개 이상 추가 권장")
            if "이미지 캡션" in failed:
                recs.append(f"[blog] {label} — 이미지 아래 캡션 한 줄 추가 권장")
            for check_name, check in failed.items():
                if check_name in ("메타 설명(description)", "H1 태그", "타겟 키워드 포함", "내부 링크 섹션", "이미지 캡션"):
                    continue
                recs.append(f"[blog] {check_name}: {check['message']}")
            continue

        for check in page.get("checks", []):
            if not check["passed"]:
                recs.append(f"[{page['page_type']}] {check['name']}: {check['message']}")

    return recs[:20]


def _save_audit_history(results):
    history = []
    if os.path.exists(AUDIT_PATH):
        try:
            with open(AUDIT_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    history.append(results)
    history = history[-30:]
    with open(AUDIT_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_latest_audit():
    if not os.path.exists(AUDIT_PATH):
        return None
    try:
        with open(AUDIT_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
        return history[-1] if history else None
    except Exception:
        return None
