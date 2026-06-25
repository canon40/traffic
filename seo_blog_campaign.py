"""
seo_blog_campaign.py
=====================
520위 밖 상품들의 10위권 진입을 위한 타겟 블로그 캠페인 엔진

전략:
  - 각 미노출 상품의 타겟 키워드에 맞춤화된 블로그 초안 자동 생성
  - 키워드를 제목·소제목·본문 상단 300자 내에 자연스럽게 배치 (SEO 최적화)
  - 내부 링크(상품 페이지 → 블로그 → 다시 상품)로 클릭 시그널 강화
  - blog_drafts/{상품명}/ 폴더에 날짜별로 HTML 저장

사용법:
    python seo_blog_campaign.py                   # 전체 미노출 상품 캠페인
    python seo_blog_campaign.py --product "나눔랩 코팅제 A"
    python seo_blog_campaign.py --from-report     # keyword_opportunity_report.json 활용
    python seo_blog_campaign.py --count 3         # 상품당 글 수 지정
"""

import sys
import os
import json
import re
import time
import random
import argparse
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)

# AI 라이브러리 (선택적)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# ── 경로 설정 ────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CREDS_PATH = os.path.join(BASE_DIR, "security_vault", "credentials.json")
OPPORTUNITY_REPORT = os.path.join(BASE_DIR, "keyword_opportunity_report.json")
DRAFT_BASE_DIR = os.path.join(BASE_DIR, "blog_drafts")

STORE_URL = "https://smartstore.naver.com/nanumlab"

# ── 상품별 마케팅 포인트 ─────────────────────────────────────────
PRODUCT_SELLING_POINTS = {
    "퍼마코트": {
        "usp": "나노 SiO₂ 유리막 기술로 6~12개월 지속",
        "target_pain": "세차 후에도 금방 더러워지는 차 때문에 스트레스받는",
        "benefit": "한 번 시공으로 반년 이상 광택과 발수 효과 유지",
        "proof": "실사용자 ★4.8 리뷰, 2만+ 판매 돌파",
        "cta": "전문점 수십만원 vs 셀프 퍼마코트 단 몇 만원",
    },
    "리빙코트": {
        "usp": "가구·실내 전용 수성 코팅제, 냄새 없음",
        "target_pain": "가구 표면이 긁히고 오염돼서 교체를 고민하는",
        "benefit": "코팅 한 번으로 가구 수명 2~3배 연장",
        "proof": "원목·가죽·합판 모두 사용 가능한 다목적 코팅제",
        "cta": "새 가구 살 돈으로 기존 가구를 새것처럼",
    },
    "코팅제": {
        "usp": "공장 직영 판매 — 중간 마진 없는 가성비 코팅제",
        "target_pain": "비싼 코팅제를 사봤지만 효과가 기대에 못 미쳤던",
        "benefit": "자동차 도장면 보호 + 광택 + 발수 3가지 동시 해결",
        "proof": "나눔랩 직영 스마트스토어 정품 보장",
        "cta": "지금 바로 집에서 셀프 시공 가능",
    },
    "세정": {
        "usp": "강력 세정력 + 도장 무해 이중 설계",
        "target_pain": "세차를 해도 찌든 때가 안 지워져 고민인",
        "benefit": "1회 도포로 철분·물때·유막 동시 제거",
        "proof": "중성 pH 설계로 도장 손상 없이 안전하게 세정",
        "cta": "전문 세차장 안 가고 집에서 해결",
    },
}

INTENT_RULES = {
    "review": "후기형",
    "comparison": "비교형",
    "howto": "방법형",
    "problem_solution": "문제해결형",
}

# ── 블로그 글 구조 템플릿 ────────────────────────────────────────
POST_STRUCTURES = [
    # 구조 A: 문제 → 원인 → 해결
    {
        "name": "문제해결형",
        "outline": [
            "서론: 독자의 공감 유도 (문제 제시)",
            "H2: 왜 이 문제가 반복될까? (원인 분석)",
            "H2: 전문가가 추천하는 해결법",
            "H2: 셀프 시공 단계별 가이드",
            "H2: 실제 사용 후기 & 결과",
            "결론: 제품 CTA",
        ],
    },
    # 구조 B: 비교 → 선택 가이드
    {
        "name": "비교선택형",
        "outline": [
            "서론: '어떤 제품을 골라야 할까?' 공감",
            "H2: 시중 제품 비교 기준 3가지",
            "H2: 유형별 장단점 정직 비교",
            "H2: 나눔랩이 선택받는 이유",
            "H2: 구매 전 체크리스트",
            "결론: 제품 CTA",
        ],
    },
    # 구조 C: 노하우 공유형
    {
        "name": "노하우공유형",
        "outline": [
            "서론: 경험담으로 시작 (신뢰 형성)",
            "H2: 절대 하면 안 되는 실수 TOP 3",
            "H2: 프로가 알려주는 올바른 방법",
            "H2: 효과를 2배로 높이는 꿀팁",
            "H2: Q&A (자주 묻는 질문)",
            "결론: 제품 CTA",
        ],
    },
]

REFERENCE_IMAGES = [
    "https://images.unsplash.com/photo-1607860108855-64acf2078ed9?w=700&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1520340356584-f9917d1ecc6f?w=700&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1563720223185-11003d516935?w=700&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1502161254066-6c74afbf07aa?w=700&auto=format&fit=crop",
    "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=700&auto=format&fit=crop",
]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_credentials():
    if os.path.exists(CREDS_PATH):
        with open(CREDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _get_selling_point(product_name):
    for key, sp in PRODUCT_SELLING_POINTS.items():
        if key in product_name:
            return sp
    return PRODUCT_SELLING_POINTS["코팅제"]


def _get_product_url(config, product_id):
    for p in config.get("products", []):
        if str(p.get("id")) == str(product_id):
            return p.get("url", STORE_URL)
    return STORE_URL


def _infer_intent(keyword, product_name):
    if any(token in keyword for token in ("후기", "리뷰", "해봤")):
        return "review"
    if any(token in keyword for token in ("비교", "가성비", "가격")):
        return "comparison"
    if any(token in keyword for token in ("방법", "순서", "사용법", "DIY", "셀프", "직접")):
        return "howto"
    if any(token in keyword for token in ("장마", "신차", "중고차", "광택", "발수", "관리")):
        return "problem_solution"
    if "리빙코트" in keyword or "가구" in keyword or "원목" in keyword:
        return "howto"
    if "퍼마코트" in product_name:
        return "review"
    return "comparison"


class SeoBlogCampaignEngine:
    def __init__(self, logger=None):
        self.logger = logger or print
        self.config = load_config()
        self.creds = load_credentials()
        self.ai_provider = "template"
        self.gemini_model = None
        self._init_ai()
        os.makedirs(DRAFT_BASE_DIR, exist_ok=True)

    def log(self, msg):
        self.logger(f"[SEO캠페인] {msg}")

    def _init_ai(self):
        gemini_key = self.creds.get("gemini_api_key", "").strip()
        if GEMINI_AVAILABLE and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                self.ai_provider = "gemini"
                self.log("✅ AI: Gemini 1.5 Flash 연동")
                return
            except Exception as e:
                self.log(f"⚠️ Gemini 초기화 실패: {e}")
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()
                self.ai_provider = "ollama"
                self.log("✅ AI: Ollama 연동")
                return
            except Exception:
                pass
        self.log("💡 AI: 내장 SEO 최적화 템플릿 모드")

    def _build_seo_prompt(self, keyword, product_name, product_url, sp, structure):
        outline_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(structure["outline"]))
        intent = INTENT_RULES[_infer_intent(keyword, product_name)]
        return (
            f"당신은 '나눔랩' 소속 15년 차 제품 전문가입니다.\n"
            f"아래 SEO 최적화 블로그 글을 작성해 주세요.\n\n"
            f"[타겟 키워드] {keyword}\n"
            f"[상품명] {product_name}\n"
            f"[문서 유형] {intent}\n"
            f"[상품 USP] {sp['usp']}\n"
            f"[타겟 고객] {sp['target_pain']} 분들\n"
            f"[핵심 혜택] {sp['benefit']}\n\n"
            f"[글 구조 — {structure['name']}]\n{outline_text}\n\n"
            f"[SEO 규칙]\n"
            f"1. 인사말이나 뻔한 서론 없이 첫 문단에 결론과 핵심 요약 3가지를 먼저 배치\n"
            f"2. 한 문단은 최대 3문장까지, 문단 사이 공백 유지\n"
            f"3. 본문 첫 200자 안에 '{keyword}'와 '{product_name}'를 모두 포함\n"
            f"4. 질문형 H2를 2개 이상 포함하고, 비교/비용/방법 질문 중 하나를 반드시 사용\n"
            f"5. 표 1개 이상, 리스트 1개 이상 포함\n"
            f"6. 직접 써 본 듯한 장점 1개와 아쉬운 점 1개를 모두 포함\n"
            f"7. 같은 키워드를 기계적으로 반복하지 말고 5회 이하로 제한\n"
            f"8. '~라고 합니다'보다 '~를 확인했음', '~해 본 결과' 같은 경험형 어조 사용\n"
            f"9. 본문 중간에 상품 링크 1개 포함: {product_url}\n\n"
            f"반드시 아래 JSON만 반환 (마크다운 코드블록 없이):\n"
            '{"title": "SEO 최적화 제목", "body": "HTML 본문 (h2, p, strong, ul, ol, blockquote 태그 사용)"}'
        )

    def _generate_with_ai(self, keyword, product_name, product_url, sp, structure):
        prompt = self._build_seo_prompt(keyword, product_name, product_url, sp, structure)

        if self.ai_provider == "gemini" and self.gemini_model:
            try:
                response = self.gemini_model.generate_content(prompt)
                content = response.text.strip()
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content).strip()
                data = json.loads(content)
                return data.get("title", ""), data.get("body", "")
            except Exception as e:
                self.log(f"⚠️ Gemini 실패, 템플릿 전환: {e}")

        if OLLAMA_AVAILABLE and self.ai_provider == "ollama":
            try:
                response = ollama.chat(
                    model="llama3",
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response["message"]["content"].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                data = json.loads(content)
                return data.get("title", ""), data.get("body", "")
            except Exception as e:
                self.log(f"⚠️ Ollama 실패, 템플릿 전환: {e}")

        return self._generate_template(keyword, product_name, product_url, sp, structure)

    def _generate_template(self, keyword, product_name, product_url, sp, structure):
        """SEO 최적화 내장 템플릿 — 규칙형 구조 강제"""
        today = datetime.now().strftime("%Y년 %m월 %d일")
        img_url = random.choice(REFERENCE_IMAGES)
        intent = _infer_intent(keyword, product_name)

        kw_parts = keyword.split()
        kw_variant1 = " ".join(kw_parts[::-1]) if len(kw_parts) > 1 else keyword + " 방법"
        kw_variant2 = kw_parts[0] + " 제품" if kw_parts else keyword

        title_map = {
            "review": f"{keyword} 직접 써 본 결론 | {product_name}",
            "comparison": f"{keyword} 비교 기준 정리 | {product_name}",
            "howto": f"{keyword} 방법 정리 | {product_name}",
            "problem_solution": f"{keyword} 해결 포인트 | {product_name}",
        }
        title = title_map[intent]

        body = f"""
<div style="line-height:1.9;font-family:'Noto Sans KR',sans-serif;color:#222;max-width:720px;margin:0 auto;">

  <p style="background:#f0f9f0;border-left:4px solid #2db400;padding:14px 18px;border-radius:4px;font-size:0.97em;">
    <strong>핵심 요약:</strong> {keyword}을 찾는다면 먼저 결론부터 보시면 됩니다. 
    나눔랩 {product_name}는 {sp['benefit']} 쪽에서 체감이 있었고, 작업 전 준비와 도포량이 결과를 크게 좌우했습니다.
  </p>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    {keyword}에서 먼저 봐야 할 포인트는 무엇일까?
  </h2>
  <p>
    {keyword}을 찾는 분들은 보통 {sp['target_pain']} 경우가 많았습니다.
    직접 써 본 결과 제품 자체보다 표면 준비와 얇은 도포가 만족도를 더 크게 바꿨습니다.
  </p>

  <br>
  <img src="{img_url}" alt="{keyword} 사용 사례" style="max-width:100%;border-radius:12px;margin:16px 0;">
  <p style="font-size:0.85em;color:#888;text-align:center;margin-top:-8px;">나눔랩 {product_name} 시공 전·후 비교</p>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    {kw_variant1} 비교 기준은 어떻게 잡는 게 좋을까?
  </h2>
  <table style="width:100%;border-collapse:collapse;margin:12px 0 20px 0;">
    <tr><th style="text-align:left;border-bottom:1px solid #ddd;padding:10px;">비교 항목</th><th style="text-align:left;border-bottom:1px solid #ddd;padding:10px;">직접 본 포인트</th></tr>
    <tr><td style="padding:10px;border-bottom:1px solid #eee;">핵심 키워드</td><td style="padding:10px;border-bottom:1px solid #eee;">{keyword}</td></tr>
    <tr><td style="padding:10px;border-bottom:1px solid #eee;">체감 장점</td><td style="padding:10px;border-bottom:1px solid #eee;">{sp['benefit']}</td></tr>
    <tr><td style="padding:10px;border-bottom:1px solid #eee;">아쉬운 점</td><td style="padding:10px;border-bottom:1px solid #eee;">초반 도포량 감각을 익히는 시간이 필요했음</td></tr>
    <tr><td style="padding:10px;border-bottom:1px solid #eee;">선택 이유</td><td style="padding:10px;border-bottom:1px solid #eee;">{sp['usp']}</td></tr>
  </table>
  <ul style="line-height:2.1;">
    <li>너무 긴 설명보다 작업 난이도와 유지 편의성부터 보는 쪽이 실제 선택에 도움 됐습니다.</li>
    <li>발수감과 광택은 보였지만, 첫 시공 때는 한 패널씩 나눠 바르는 방식이 더 안정적이었습니다.</li>
    <li><a href="{product_url}" target="_blank" style="color:#2db400;font-weight:bold;text-decoration:underline;">스마트스토어 상품 링크</a>는 중간에 한 번만 넣어 흐름을 끊지 않게 구성했습니다.</li>
  </ul>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    집에서 {kw_variant2} 쓰는 순서는 어떻게 잡아야 할까?
  </h2>
  <ol style="line-height:2.4;">
    <li><strong>표면 정리</strong><br>먼지와 유분을 먼저 없애야 결과 차이가 컸습니다.</li>
    <li><strong>소량 도포</strong><br>처음부터 많이 바르기보다 얇게 여러 번 나누는 편이 얼룩이 적었습니다.</li>
    <li><strong>경화 대기</strong><br>바른 직후 바로 닦기보다 잠깐 기다린 뒤 잔사를 정리하는 쪽이 균일했습니다.</li>
    <li><strong>최종 확인</strong><br>발수 테스트와 표면 촉감을 함께 봐야 체감 차이를 판단하기 쉬웠습니다.</li>
  </ol>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    직접 써 보니 아쉬운 점은 없었을까?
  </h2>
  <p>
    {keyword}을 기준으로 보면 장점은 분명했습니다. 특히 {sp['benefit']} 쪽은 직접 확인했을 때 차이가 남았습니다.
  </p>
  <p>
    다만 첫 시공에서는 양 조절이 생각보다 중요했고, 너무 서두르면 닦임 자국이 남을 수 있었습니다.
  </p>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    {keyword} 비용은 얼마나 들까?
  </h2>
  <p>
    전문 시공과 비교하면 초기 비용은 줄일 수 있었지만, 작업 시간을 직접 쓰는 만큼 준비물과 순서를 미리 확인하는 편이 효율적이었습니다.
  </p>

  <h2 style="color:#1a1a1a;border-left:4px solid #2db400;padding-left:14px;margin-top:36px;">
    {keyword} 초보자도 바로 할 수 있을까?
  </h2>
  <p>
    가능했습니다. 다만 작은 면적부터 시작하고, 작업 사이사이 표면 상태를 확인하는 방식이 실패 확률을 줄여줬습니다.
  </p>

  <div style="background:#f6f7f8;border-radius:12px;padding:24px;margin:32px 0;">
    <p style="font-size:1.05em;font-weight:bold;color:#1a1a1a;margin:0 0 8px;">정리하면</p>
    <p style="color:#555;margin:0 0 12px;font-size:0.95em;">{sp['cta']}</p>
    <p style="margin:0;"><a href="{product_url}" target="_blank" style="color:#2db400;font-weight:bold;text-decoration:underline;">나눔랩 {product_name} 자세히 보기</a></p>
  </div>

</div>
"""
        return title, body

    def _inject_internal_links(self, body, product_url, keyword):
        """본문 내 키워드에 상품 링크 자동 삽입 (첫 번째 등장만)"""
        link_html = (
            f'<a href="{product_url}" target="_blank" '
            f'style="color:#2db400;font-weight:bold;text-decoration:underline;">'
            f"{keyword}</a>"
        )
        # 첫 번째 키워드 등장에만 링크 삽입
        if keyword in body:
            body = body.replace(keyword, link_html, 1)
        return body

    def generate_draft(self, product, keyword, structure=None):
        """한 상품의 특정 키워드용 블로그 초안 생성"""
        pid = str(product.get("id", ""))
        name = product.get("name", pid)
        product_url = _get_product_url(self.config, pid)
        sp = _get_selling_point(name)
        structure = structure or random.choice(POST_STRUCTURES)

        self.log(f"✏️ '{keyword}' 글 작성 중... [{name}]")
        title, body = self._generate_with_ai(keyword, name, product_url, sp, structure)

        if not title:
            title = f"{keyword} 완벽 가이드 — 나눔랩 {name} 활용법"

        # 내부 링크 삽입
        body = self._inject_internal_links(body, product_url, keyword)

        return title, body, product_url

    def save_draft(self, product_name, keyword, title, body):
        """상품별 서브폴더에 HTML 초안 저장"""
        safe_pname = re.sub(r'[\\/:"*?<>|]', "_", product_name)[:30]
        safe_kw = re.sub(r'[\\/:"*?<>|]', "_", keyword)[:25]
        ts = datetime.now().strftime("%m%d_%H%M")
        subdir = os.path.join(DRAFT_BASE_DIR, safe_pname)
        os.makedirs(subdir, exist_ok=True)
        filename = os.path.join(subdir, f"{ts}_{safe_kw}.html")

        html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{title} — 나눔랩 공식 제품 상세 정보">
<title>{title}</title>
<style>
  body {{ font-family: 'Noto Sans KR', sans-serif; max-width: 740px;
         margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.9; }}
  .meta {{ font-size: 0.85em; color: #888; margin-bottom: 32px; }}
  .keyword-tag {{ display: inline-block; background: #e8f5e9; color: #2db400;
                  padding: 3px 10px; border-radius: 20px; font-size: 0.8em;
                  font-weight: bold; margin-right: 6px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">
  <span class="keyword-tag"># {keyword}</span>
  <span class="keyword-tag"># {product_name}</span>
  작성일: {datetime.now().strftime("%Y년 %m월 %d일")} | 나눔랩 공식 블로그
</div>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
{body}
</body>
</html>"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        return filename

    def run_campaign(self, target_product_name=None, posts_per_product=3, use_report=False):
        """전체 미노출 상품 블로그 캠페인 실행"""
        config = self.config
        products = config.get("products", [])

        if target_product_name:
            products = [p for p in products if p.get("name") == target_product_name]

        # keyword_opportunity_report.json 활용
        opportunity_map = {}
        if use_report and os.path.exists(OPPORTUNITY_REPORT):
            try:
                with open(OPPORTUNITY_REPORT, "r", encoding="utf-8") as f:
                    report = json.load(f)
                for pid, data in report.get("results", {}).items():
                    top_kws = [
                        k["keyword"]
                        for k in data.get("top_keywords", [])[:posts_per_product]
                    ]
                    opportunity_map[pid] = top_kws
                self.log(f"✅ 키워드 리포트 로드 완료 ({len(opportunity_map)}개 상품)")
            except Exception as e:
                self.log(f"⚠️ 리포트 로드 실패: {e}")

        # 미노출 상품 필터 (520위 밖 기준)
        UNRANKED_PRODUCT_IDS = [
            "12639296730",  # 퍼마코트 자동차 코팅제 (셀프 유리막 코팅 키워드 미노출)
            "12634187514",  # 나눔랩 코팅 상품
            "12808787263",  # 나눔랩 세정·관리제
            "12808820913",  # 나눔랩 코팅제 A
            "12809519826",  # 나눔랩 코팅제 B
            "12809532969",  # 나눔랩 코팅제 C
            "12809541448",  # 나눔랩 코팅제 D
        ]

        if not target_product_name:
            # 전체 실행 시 미노출 상품만 대상
            products = [p for p in products if str(p.get("id")) in UNRANKED_PRODUCT_IDS]

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*60}")
        print(f"📝 나눔랩 SEO 블로그 캠페인 — {now}")
        print(f"{'='*60}")
        print(f"대상 상품: {len(products)}개 | 상품당 포스팅: {posts_per_product}개")
        print(f"AI 엔진: {self.ai_provider}")
        print(f"{'='*60}\n")

        total_saved = []

        for product in products:
            pid = str(product.get("id", ""))
            name = product.get("name", pid)
            print(f"\n[{name}] 캠페인 시작...")

            # 키워드 결정 (리포트 우선, 없으면 config fallback)
            if pid in opportunity_map:
                keywords = opportunity_map[pid][:posts_per_product]
            else:
                # config.json의 해당 상품 키워드 활용
                kws = [
                    k["keyword"]
                    for k in config.get("keywords", [])
                    if str(k.get("product_id")) == pid
                ]
                keywords = kws[:posts_per_product] if kws else [name.split()[0]]

            if not keywords:
                self.log(f"⚠️ [{name}] 키워드 없음 — 건너뜀")
                continue

            for i, kw in enumerate(keywords):
                structure = POST_STRUCTURES[i % len(POST_STRUCTURES)]
                try:
                    title, body, product_url = self.generate_draft(product, kw, structure)
                    saved_path = self.save_draft(name, kw, title, body)
                    total_saved.append(saved_path)
                    print(f"  ✅ 저장: {os.path.basename(saved_path)}")
                    print(f"     제목: {title[:60]}...")
                except Exception as e:
                    self.log(f"❌ [{name}][{kw}] 실패: {e}")

                if i < len(keywords) - 1:
                    time.sleep(1)

        print(f"\n{'='*60}")
        print(f"🎉 캠페인 완료! 총 {len(total_saved)}개 초안 생성")
        print(f"📂 저장 위치: {DRAFT_BASE_DIR}")
        print(f"{'='*60}")
        for path in total_saved:
            rel = os.path.relpath(path, BASE_DIR)
            print(f"  • {rel}")

        return total_saved


def main():
    parser = argparse.ArgumentParser(description="나눔랩 SEO 블로그 캠페인")
    parser.add_argument("--product", type=str, default="", help="특정 상품명만 실행")
    parser.add_argument("--count", type=int, default=3, help="상품당 포스팅 수 (기본 3)")
    parser.add_argument(
        "--from-report", action="store_true",
        help="keyword_opportunity_report.json 기반 키워드 사용"
    )
    args = parser.parse_args()

    engine = SeoBlogCampaignEngine()
    engine.run_campaign(
        target_product_name=args.product or None,
        posts_per_product=args.count,
        use_report=args.from_report,
    )


if __name__ == "__main__":
    main()
