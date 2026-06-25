"""
SEO 개선 권장 항목 → 붙여넣기용 가이드·블로그 초안 생성.

사용법:
  python seo_fixes.py
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

CONFIG_PATH = Path("config.json")
OUTPUT_DIR = Path("generated_content")
BLOG_DRAFT_DIR = Path("blog_drafts")


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _product_id(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    if len(parts) >= 3 and parts[-2] == "products":
        return parts[-1]
    return ""


def _clamp_meta(text: str, min_len: int = 50, max_len: int = 160) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def build_blog_body(h1: str, keywords: list[str], brand: str = "나눔랩") -> str:
    kw_line = ", ".join(keywords)
    return f"""# {h1}

**{keywords[0]}**와 **{keywords[1]}**를 직접 사용해 본 경험을 정리했습니다.
검색하시는 분들이 궁금해하는 **{kw_line}** 키워드를 중심으로 후기와 사용 팁을 공유합니다.

## 왜 {keywords[0]}를 알아보게 됐나요

차량·가구 관리 비용을 줄이면서도 광택과 발수 효과를 원하셨다면,
{keywords[1]} 셀프 시공이 합리적인 선택입니다.

## {keywords[2]}와 함께 보면 좋은 이유

자동차는 {keywords[0]}, 가구·원목은 {keywords[2]}로 나누어 관리하면
코팅 효과를 균형 있게 유지할 수 있습니다.

## 총평

{keywords[0]} · {keywords[1]} · {keywords[2]}를 모두 검색하시는 분들께
과장 없는 사용 후기와 구매 전 체크리스트를 참고해 주세요.
"""


def generate_paste_guide(config: dict) -> str:
    lines = [
        "# 나눔랩 SEO 붙여넣기 가이드",
        f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 상품 — 스마트스토어센터 → SEO 설정 → 메타 설명",
        "",
    ]

    product_seo = config.get("product_seo", {})
    for p in config.get("products", []):
        pid = str(p.get("id", ""))
        seo = product_seo.get(pid)
        if not seo:
            continue
        meta = _clamp_meta(seo.get("meta_description", ""))
        lines.extend([
            f"### {p.get('name')} (`{pid}`)",
            f"- URL: {p.get('url', '')}",
            f"- 메타 설명 ({len(meta)}자):",
            "",
            meta,
            "",
        ])

    lines.extend(["## 블로그 — 블로그 관리 → 기본 설정 / 글 SEO", ""])
    for url, seo in config.get("blog_seo", {}).items():
        meta = _clamp_meta(seo.get("meta_description", ""))
        h1 = seo.get("h1", "")
        lines.extend([
            f"### {seo.get('label', url)}",
            f"- URL: {url}",
            f"- 메타 설명 ({len(meta)}자):",
            "",
            meta,
            "",
            f"- H1 (글 제목·본문에 1개만): **{h1}**",
            f"- 포함 키워드: {', '.join(seo.get('keywords', []))}",
            "",
        ])

    return "\n".join(lines)


def write_blog_drafts(config: dict) -> list[str]:
    BLOG_DRAFT_DIR.mkdir(exist_ok=True)
    saved = []
    brand = config.get("brand", "나눔랩")

    for url, seo in config.get("blog_seo", {}).items():
        label = seo.get("label") or "blog"
        meta = _clamp_meta(seo.get("meta_description", ""))
        h1 = seo.get("h1", "나눔랩 코팅 후기")
        keywords = seo.get("keywords") or ["자동차코팅제", "셀프 유리막 코팅", "듀라코트 리빙코트"]
        body = build_blog_body(h1, keywords, brand=brand)

        content = f"""---
blog_url: {url}
meta_description: {meta}
h1: {h1}
keywords: {', '.join(keywords)}
---

<!-- 네이버 블로그: 설정 > 블로그 관리 > 검색·메타 정보에 아래 설명 붙여넣기 -->
<!-- 메타 설명 ({len(meta)}자) -->
{meta}

{body}
"""
        path = BLOG_DRAFT_DIR / f"seo_fix_{label}.md"
        path.write_text(content, encoding="utf-8")
        saved.append(str(path))

    return saved


def run() -> dict:
    config = load_config()
    OUTPUT_DIR.mkdir(exist_ok=True)

    guide = generate_paste_guide(config)
    guide_path = OUTPUT_DIR / "SEO_붙여넣기_가이드.md"
    guide_path.write_text(guide, encoding="utf-8")

    drafts = write_blog_drafts(config)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "guide_path": str(guide_path),
        "blog_drafts": drafts,
        "product_seo": config.get("product_seo", {}),
        "blog_seo": config.get("blog_seo", {}),
    }
    manifest_path = OUTPUT_DIR / "seo_fixes_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"가이드: {guide_path}")
    for d in drafts:
        print(f"블로그 초안: {d}")
    return manifest


if __name__ == "__main__":
    run()
