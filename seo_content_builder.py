import json
import os
import re
from datetime import datetime

CONFIG_PATH = "config.json"
OUTPUT_DIR = "generated_content"

WORKFLOW_TYPES = {
    "product_detail": "상품 상세페이지 (ABCD)",
    "blog_review": "블로그 체험 후기",
    "comparison": "비교·선택 가이드",
    "howto": "사용법 튜토리얼",
    "faq": "FAQ 블록",
    "meta_tags": "상품명·태그·메타",
    "seasonal": "시즌 캠페인",
    "benefit": "핵심 혜택 요약",
    "trust": "신뢰·인증 강조",
    "cta": "구매 유도 CTA",
}

DEFAULT_CONTENT_RULES = {
    "max_sentences_per_paragraph": 3,
    "intro_keyword_window": 200,
    "max_keyword_repeats": 5,
    "require_table": True,
    "require_list": True,
    "require_qna_count": 2,
    "require_experience_lines": 2,
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"store_name": "나눔랩", "brand": "나눔랩"}


def _content_rules(config: dict) -> dict:
    rules = dict(DEFAULT_CONTENT_RULES)
    rules.update(config.get("content_rules") or {})
    return rules


def _infer_intent(keyword: str, product_name: str) -> str:
    keyword = keyword.strip()
    if any(token in keyword for token in ("후기", "해봤", "리뷰")):
        return "review"
    if any(token in keyword for token in ("비교", "가성비", "가격")):
        return "comparison"
    if any(token in keyword for token in ("방법", "순서", "사용법", "직접", "DIY", "셀프")):
        return "howto"
    if any(token in keyword for token in ("장마", "중고차", "신차", "광택", "발수", "관리")):
        return "problem_solution"
    if "리빙코트" in keyword or "가구" in keyword or "원목" in keyword:
        return "howto"
    if "퍼마코트" in product_name or "자동차" in keyword:
        return "review"
    return "comparison"


def _smartstore_link(product_name: str) -> str:
    return f"[{product_name} 스마트스토어 바로가기](상품 링크를 여기에 붙여넣기)"


def _keyword_variants(keyword: str) -> list[str]:
    base = [keyword]
    if "자동차코팅제" in keyword:
        base.extend(["차량 코팅제", "셀프 코팅"])
    elif "리빙코트" in keyword:
        base.extend(["가구 코팅", "원목 코팅"])
    elif "유리막" in keyword:
        base.extend(["유리막 코팅", "발수 코팅"])
    return list(dict.fromkeys(base))


def _experience_lines(product_name: str, keyword: str) -> list[str]:
    return [
        f"{product_name}를 써 본 결과, {keyword} 관련 검색에서 많이 언급되는 발수감은 분명히 체감됐습니다.",
        "좋았던 점만 적기보다, 처음 도포할 때 양 조절이 생각보다 중요하다는 점도 같이 적어두는 편이 신뢰에 도움이 됩니다.",
        "직접 해 보니 작업 시간은 짧았지만, 표면 정리와 건조를 대충 하면 결과 차이가 크게 났습니다.",
    ]


def _comparison_table(product_name: str, keyword: str) -> str:
    return (
        "| 비교 항목 | 직접 확인한 포인트 |\n"
        "| --- | --- |\n"
        f"| 핵심 키워드 | {keyword} |\n"
        f"| 추천 제품 | 나눔랩 {product_name} |\n"
        "| 체감 장점 | 발수감, 관리 편의성, 광택 유지 |\n"
        "| 아쉬운 점 | 초반 도포량을 맞추는 연습이 필요 |\n"
    )


def _qna_block(keyword: str, product_name: str) -> str:
    return (
        f"## {keyword} 비용은 얼마나 들까?\n"
        f"정답은 작업 범위에 따라 다르지만, 전문 시공 대비 {product_name} 셀프 작업이 예산을 줄이는 데 유리했습니다.\n\n"
        f"## {keyword} 초보자도 바로 할 수 있을까?\n"
        "준비물만 갖춰 두면 가능했지만, 첫 작업은 작은 면적부터 시작하는 쪽이 확실히 안전했습니다."
    )


def _normalize_paragraphs(text: str, max_sentences: int) -> str:
    chunks = []
    for block in text.split("\n\n"):
        stripped = block.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|") or stripped.startswith("- ") or stripped.startswith("1. "):
            chunks.append(stripped)
            continue
        sentences = re.split(r"(?<=[.!?])\s+", stripped)
        current = []
        for sentence in sentences:
            if not sentence:
                continue
            current.append(sentence)
            if len(current) >= max_sentences:
                chunks.append(" ".join(current).strip())
                current = []
        if current:
            chunks.append(" ".join(current).strip())
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _abcd_product_detail(keyword, product_name, brand):
    return {
        "workflow": "product_detail",
        "title": f"{keyword} | {product_name} - {brand}",
        "sections": {
            "A_주목": (
                f"차량 외장이 금방 흐려지고 물때가 남나요?\n"
                f"'{keyword}'를 검색하신 분들이 가장 먼저 겪는 고민입니다."
            ),
            "B_이점": (
                f"• 셀프 작업으로 전문 코팅샵급 광택 구현\n"
                f"• 발수·오염 방지로 세차 횟수 감소\n"
                f"• {brand} {product_name} — 초보자도 균일하게 도포 가능"
            ),
            "C_근거": (
                f"• 실사용 전후 비교 사진·영상 배치 권장\n"
                f"• 성분·도포 방법·유지 기간을 숫자로 명시\n"
                f"• 구매자 리뷰에서 '{keyword}' 관련 키워드가 자연스럽게 등장하도록 유도"
            ),
            "D_행동유도": (
                f"지금 바로 {product_name} 상세페이지에서 용량·구성을 확인하세요.\n"
                f"첫 구매 고객 대상 사용 가이드 PDF를 함께 제공하면 체류 시간이 늘어납니다."
            ),
        },
        "seo_tags": [keyword, brand, product_name, "셀프코팅", "유리막코팅", "자동차관리"],
        "meta_description": (
            f"{brand} {product_name} — {keyword} 추천. "
            f"셀프 유리막 코팅으로 광택·발수·오염 방지를 한 번에. 사용법·후기·구매 안내."
        )[:160],
    }


def _blog_review(keyword, product_name, brand, rules):
    intent = _infer_intent(keyword, product_name)
    keywords = _keyword_variants(keyword)
    h1 = f"{keyword} 핵심 정리 | {product_name} 직접 써 본 결론"
    meta = (
        f"{brand} {product_name} 기준으로 {keyword} 핵심 포인트를 먼저 정리했습니다. "
        "비교표, 사용 순서, 직접 써 본 장단점과 Q&A를 함께 확인할 수 있습니다."
    )
    meta = meta[:160] if len(meta) <= 160 else meta[:157] + "…"

    intro = (
        f"{keyword}를 찾는 분이라면 결론부터 보시면 됩니다. "
        f"{brand} {product_name}는 초보자도 접근하기 쉬웠고, 발수감과 관리 편의성 쪽에서 차이가 있었습니다. "
        "아래에 바로 비교표와 실제 사용 포인트를 정리했습니다."
    )
    experience = _experience_lines(product_name, keyword)
    sections = {
        "review": (
            f"## 먼저 결론\n{intro}\n\n"
            f"## 직접 써 보고 느낀 점\n{experience[0]}\n\n{experience[1]}\n\n"
            f"## 비교표\n{_comparison_table(product_name, keyword)}\n\n"
            f"## 사용하면서 아쉬웠던 점\n{experience[2]}\n\n"
            f"{_qna_block(keyword, product_name)}\n\n"
            f"## 정리\n{_smartstore_link(product_name)}"
        ),
        "comparison": (
            f"## 먼저 결론\n{intro}\n\n"
            f"## 비교 기준 3가지\n- 가격 대비 체감 효과\n- 도포 난이도\n- 유지 관리 편의성\n\n"
            f"## 비교표\n{_comparison_table(product_name, keyword)}\n\n"
            f"## 직접 비교하며 본 차이\n{experience[0]}\n\n{experience[2]}\n\n"
            f"{_qna_block(keyword, product_name)}\n\n"
            f"## 선택 팁\n{_smartstore_link(product_name)}"
        ),
        "howto": (
            f"## 먼저 결론\n{intro}\n\n"
            f"## 준비 순서\n1. 표면 세척\n2. 충분한 건조\n3. 소량 도포\n4. 잔사 정리\n\n"
            f"## 작업 체크표\n{_comparison_table(product_name, keyword)}\n\n"
            f"## 직접 해 보니 주의할 점\n{experience[0]}\n\n{experience[1]}\n\n"
            f"{_qna_block(keyword, product_name)}\n\n"
            f"## 마무리\n{_smartstore_link(product_name)}"
        ),
        "problem_solution": (
            f"## 먼저 결론\n{intro}\n\n"
            f"## 이런 경우에 체감이 컸음\n- 장마철 물때 관리\n- 신차 초기 보호\n- 중고차 외장 정리\n\n"
            f"## 해결 포인트 표\n{_comparison_table(product_name, keyword)}\n\n"
            f"## 직접 확인한 효과와 한계\n{experience[0]}\n\n{experience[2]}\n\n"
            f"{_qna_block(keyword, product_name)}\n\n"
            f"## 추천 대상\n{_smartstore_link(product_name)}"
        ),
    }
    body = _normalize_paragraphs(sections[intent], int(rules["max_sentences_per_paragraph"]))
    return {
        "workflow": "blog_review",
        "title": h1,
        "h1": h1,
        "meta_description": meta,
        "body": body,
        "seo_keywords": keywords,
        "intent": intent,
        "content_rules": rules,
    }


def _meta_tags(keyword, product_name, brand):
    short_name = f"{brand} {product_name} {keyword}"[:50]
    return {
        "workflow": "meta_tags",
        "product_title_suggestion": short_name,
        "tags": list(dict.fromkeys([
            keyword, brand.replace(" ", ""), "셀프코팅", "유리막",
            "자동차코팅", "차량관리", "광택", "발수코팅", "나눔랩",
        ]))[:10],
        "meta_description": _abcd_product_detail(keyword, product_name, brand)["meta_description"],
        "h1_suggestion": f"{product_name} — {keyword} 셀프 코팅 솔루션",
    }


def generate_content(workflow_type, keyword, product_name=None, brand=None):
    config = load_config()
    brand = brand or config.get("store_name", "나눔랩")
    product_name = product_name or config.get("default_product_name", "퍼마코트")
    rules = _content_rules(config)

    builders = {
        "product_detail": lambda: _abcd_product_detail(keyword, product_name, brand),
        "blog_review": lambda: _blog_review(keyword, product_name, brand, rules),
        "meta_tags": lambda: _meta_tags(keyword, product_name, brand),
        "comparison": lambda: {
            "workflow": "comparison",
            "title": f"{keyword} 비교 가이드 — 워셔형 vs 전문 코팅",
            "body": (
                f"## {keyword} 선택 시 체크리스트\n"
                f"- 도포 난이도\n- 유지 기간\n- 가격 대비 용량\n- 리뷰 평점\n\n"
                f"## {product_name} 포지션\n"
                f"셀프 작업 가능 + 합리적 가격대를 강조하세요."
            ),
        },
        "howto": lambda: {
            "workflow": "howto",
            "title": f"{product_name} 셀프 코팅 5단계",
            "steps": [
                "세차 및 완전 건조",
                "클레이·폴리싱(선택)",
                "도포량 준비 — 한 패널씩 작업",
                "균일 스프레드 후 15~30분 경화",
                "잔여물 제거 및 24시간 주차",
            ],
        },
        "faq": lambda: {
            "workflow": "faq",
            "items": [
                {"q": f"{keyword} 초보자도 가능한가요?", "a": "예, 동봉 가이드와 영상을 함께 제공하세요."},
                {"q": "유지 기간은?", "a": "사용 환경에 따라 3~6개월, 구체 수치를 명시하세요."},
                {"q": "세차 후 바로 도포?", "a": "물기·오일 잔여물 제거 후 도포를 권장합니다."},
            ],
        },
    }

    if workflow_type not in builders and workflow_type not in WORKFLOW_TYPES:
        return {"success": False, "error": f"지원하지 않는 워크플로우: {workflow_type}"}

    if workflow_type in builders:
        content = builders[workflow_type]()
    else:
        content = _abcd_product_detail(keyword, product_name, brand)
        content["workflow"] = workflow_type

    result = {
        "success": True,
        "workflow": workflow_type,
        "workflow_label": WORKFLOW_TYPES.get(workflow_type, workflow_type),
        "keyword": keyword,
        "product_name": product_name,
        "brand": brand,
        "intent": _infer_intent(keyword, product_name),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
    }
    return result


def save_content(result, product_id=None):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    wf = result.get("workflow", "content")
    pid = product_id or "general"
    path = os.path.join(OUTPUT_DIR, f"{pid}_{wf}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path


def list_workflows():
    return [{"id": k, "label": v} for k, v in WORKFLOW_TYPES.items()]
