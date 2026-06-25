import streamlit as st
import subprocess
import pandas as pd
import os
import json
import time
import io
from datetime import datetime
from pathlib import Path

# GenSpark 의존성 (없으면 graceful degradation)
try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    from dotenv import load_dotenv
    _env = Path(r"d:\@code\GEMMA4\Antigravity_Workspace\.env")
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

try:
    from pptx import Presentation
    from pptx.util import Pt
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

# GenSpark API 설정
SERPAPI_KEY    = os.getenv("SERPAPI_KEY", "")
AI_API_KEY     = os.getenv("ANTHROPIC_API_KEY", os.getenv("SKYWORK_API_KEY", ""))
AI_API_BASE    = os.getenv("SKYWORK_API_BASE", "https://api.aiprime.store/v1")

# ==========================================
# NanumLab SmartStore Dashboard (v4.0)
# ==========================================

st.set_page_config(
    page_title="나눔랩 스마트스토어 트래픽 & 순위 솔루션",
    layout="wide",
    page_icon="🛡️"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }

    .stApp { background: linear-gradient(135deg, #0d1117 0%, #161b22 100%); color: #e6edf3; }

    .stButton>button {
        background: linear-gradient(90deg, #238636 0%, #2ea043 100%);
        color: white; border: none; border-radius: 12px; height: 50px;
        font-weight: 600; transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(35,134,54,0.3);
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(35,134,54,0.4); }

    /* 상태 배지 */
    .status-running {
        background: rgba(35,134,54,0.2); border: 1px solid #238636;
        border-radius: 8px; padding: 8px 14px; color: #2ea043; font-weight: 600;
        display: inline-block; animation: pulse 1.5s infinite;
    }
    .status-idle {
        background: rgba(100,100,100,0.2); border: 1px solid #555;
        border-radius: 8px; padding: 8px 14px; color: #aaa; font-weight: 600;
        display: inline-block;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

    /* 로그 박스 */
    .log-box {
        background: #0d1117; border: 1px solid #30363d; border-radius: 12px;
        padding: 16px; font-family: 'Courier New', monospace; font-size: 13px;
        color: #7ee787; height: 320px; overflow-y: auto; white-space: pre-wrap;
    }
    .log-line-ok   { color: #7ee787; }
    .log-line-err  { color: #f85149; }
    .log-line-info { color: #79c0ff; }

    h1,h2,h3 { color: #ffffff; }

    .metric-box {
        background: #161b22; border: 1px solid #30363d; border-radius: 12px;
        padding: 18px; border-left: 4px solid #238636; margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# --- 파일 경로 ---
KEYWORD_LOG_FILE  = "keyword_rank_log.csv"
WORK_LOG_FILE     = "work_log.txt"
SYSTEM_LOG_FILE   = "traffic_service.log"  # traffic_service.py 가 기록하는 로그
CONFIG_FILE      = "traffic_config.json"
PID_FILE         = ".worker.pid"

# --- 키워드 그룹 ---
KEYWORD_GROUPS = {
    "🛠️ 리빙/인테리어": ["듀라코트 리빙코트","나노코팅","다이아몬트 코팅공법","욕실코팅제","타일코팅제","식탁코팅","원목코팅"],
    "🏍️ 바이크/오토바이": ["듀라코트 퍼마코트 바이크코팅제","유리막코팅제","오토바이 셀프 코팅","퍼마코트 티탄","퍼마코트 퀵","퍼마코트 레진","폴리실라잔 코팅","바이크 광택제"],
    "🚗 자동차/차량": ["듀라코트퍼마코트 자동차 코팅제","자동차 유리막코팅제","셀프 유리막코팅","퍼마코트 타이탄","퍼마코트 퀵","퍼마코트 레진","폴리실라잔 코팅"],
}

TARGET_URLS_LIST = [
    "https://smartstore.naver.com/nanumlab/products/10713170202",
    "https://smartstore.naver.com/nanumlab/products/12639296730",
    "https://smartstore.naver.com/nanumlab/products/12808820913",
    "https://smartstore.naver.com/nanumlab/products/12808787263",
    "https://smartstore.naver.com/nanumlab/products/12809532969",
    "https://smartstore.naver.com/nanumlab/products/12809541448",
    "https://smartstore.naver.com/nanumlab/products/12809519826",
    "https://smartstore.naver.com/nanumlab/products/12634187514",
]

# --- 프로세스 실행 여부 확인 ---
def is_worker_running() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    try:
        pid = int(Path(PID_FILE).read_text().strip())
        import psutil
        return psutil.pid_exists(pid)
    except Exception:
        return False

# --- 로그 파일 읽기 (인코딩 안전) ---
def read_log(path: str, lines: int = 40) -> str:
    if not os.path.exists(path):
        return "(로그 없음)"
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                all_lines = f.readlines()
            return "".join(all_lines[-lines:]) if all_lines else "(로그 없음)"
        except Exception:
            continue
    return "(파일 읽기 실패)"

# --- 최신 작업 키워드 추출 ---
def get_last_keyword() -> str:
    log = read_log(WORK_LOG_FILE, 5)
    for line in reversed(log.splitlines()):
        if "키워드:" in line:
            try:
                return line.split("키워드:")[1].split("|")[0].strip()
            except Exception:
                pass
    return "—"

# ============================
# SIDEBAR
# ============================
with st.sidebar:
    st.markdown("### 🎯 타겟 스토어 설정")
    selected_targets = []
    for url in TARGET_URLS_LIST:
        short = url.split("/")[-1]
        if st.checkbox(short, value=True, key=f"url_{url}"):
            selected_targets.append(url)
    st.divider()
    st.caption("🛡️ 익명성 보장: 개인정보 미포함")
    st.caption("📊 Google CSE API 기반 순위 측정")

# ============================
# MAIN
# ============================
st.title("🛡️ 나눔랩 쉴드 (NanumLab Shield)")
st.subheader("키워드 검색 순위 측정 & 트래픽 모니터링 시스템")

# --- 실시간 상태 배너 ---
running = is_worker_running()
if running:
    last_kw = get_last_keyword()
    st.markdown(f'<div class="status-running">🟢 작업 실행 중 · 현재 키워드: <b>{last_kw}</b></div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="status-idle">⚪ 대기 중 (작업 없음)</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col_main, col_side = st.columns([2, 1])

# ============================
# 키워드 선택 & 작업 시작
# ============================
with col_main:
    st.header("📋 키워드 작업 선택")
    selected_categories = []
    for group_name, keywords in KEYWORD_GROUPS.items():
        with st.expander(f"{group_name} ({len(keywords)}개)", expanded=True):
            cols = st.columns(2)
            for i, kw in enumerate(keywords):
                if cols[i % 2].checkbox(kw, value=True, key=f"kw_{group_name}_{kw}"):
                    selected_categories.append(kw)

    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        if st.button("▶ 선택한 키워드 순위 작업 시작", use_container_width=True):
            if not selected_targets:
                st.error("최소 하나 이상의 타겟 URL을 선택해주세요.")
            elif not selected_categories:
                st.error("최소 하나 이상의 키워드를 선택해주세요.")
            elif running:
                st.warning("이미 작업이 실행 중입니다.")
            else:
                # 기존 keyword_tasks에서 선택 키워드만 필터
                base_cfg = {}
                if os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        base_cfg = json.load(f)
                all_tasks = base_cfg.get("keyword_tasks") or []
                filtered_tasks = [t for t in all_tasks if t.get("keyword") in selected_categories]
                if not filtered_tasks:
                    filtered_tasks = [
                        {"keyword": kw, "mode": "boost", "priority": 8}
                        for kw in selected_categories
                    ]

                config = {
                    "products": base_cfg.get("products", {}),
                    "target_urls": selected_targets,
                    "keywords": selected_categories,
                    "keyword_tasks": filtered_tasks,
                    "boost_sessions": base_cfg.get("boost_sessions", 3),
                    "maintain_sessions": base_cfg.get("maintain_sessions", 1),
                    "max_pages": 10,
                    "stay_time_range": [45, 90],
                }
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)

                # traffic_service.py 실행 (Playwright 기반 — API 불필요)
                proc = subprocess.Popen(
                    ["python", "-u", "traffic_service.py", "--campaign", "--headless"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                Path(PID_FILE).write_text(str(proc.pid))
                st.success(f"✅ 순위 부스팅 캠페인 시작! {len(selected_categories)}개 키워드 (미발견 집중 / 1~6위 유지)")
                time.sleep(1)
                st.rerun()

    with col_btn2:
        if st.button("⏹ 작업 중지", use_container_width=True):
            if os.path.exists(PID_FILE):
                try:
                    pid = int(Path(PID_FILE).read_text().strip())
                    import psutil
                    p = psutil.Process(pid)
                    p.terminate()
                    os.remove(PID_FILE)
                    st.warning("작업을 중지했습니다.")
                except Exception as e:
                    st.error(f"중지 실패: {e}")
            else:
                st.info("실행 중인 작업이 없습니다.")

# ============================
# 현재 상태 패널
# ============================
with col_side:
    st.header("📊 현재 상황")

    # 메트릭
    total_kw = len(selected_categories)
    st.markdown(f'<div class="metric-box">🔑 선택 키워드<br><h2>{total_kw}개</h2></div>', unsafe_allow_html=True)

    if os.path.exists(KEYWORD_LOG_FILE):
        try:
            df_log = pd.read_csv(KEYWORD_LOG_FILE, on_bad_lines="skip")
            total_runs = len(df_log)
            st.markdown(f'<div class="metric-box">✅ 누적 작업<br><h2>{total_runs}회</h2></div>', unsafe_allow_html=True)
        except Exception:
            st.markdown('<div class="metric-box">✅ 누적 작업<br><h2>—</h2></div>', unsafe_allow_html=True)

    if os.path.exists("work_log.txt"):
        last_kw_disp = get_last_keyword()
        st.markdown(f'<div class="metric-box">🔍 마지막 키워드<br><b>{last_kw_disp}</b></div>', unsafe_allow_html=True)

# ============================
# 하단 탭: 로그 & 기록
# ============================
# ============================
# GenSpark 헬퍼 함수
# ============================
def gs_search(topic: str, num: int = 5) -> list:
    """SerpAPI로 웹 검색 후 콘텐츠 스크래핑"""
    if not REQUESTS_OK or not SERPAPI_KEY:
        return []
    results = []
    try:
        params = {"engine": "google", "q": topic, "api_key": SERPAPI_KEY, "num": num}
        resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
        resp.raise_for_status()
        for item in resp.json().get("organic_results", [])[:num]:
            url = item.get("link", "")
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator=" ", strip=True)[:3000]
                results.append({"url": url, "content": text})
            except Exception:
                results.append({"url": url, "content": item.get("snippet", "")})
    except Exception as e:
        st.warning(f"🔍 검색 오류: {e}")
    return results


CONTENT_PROMPTS = {
    "📊 마케팅 리포트": """다음 주제와 수집된 데이터를 바탕으로 전문적인 한국어 마케팅 분석 리포트를 작성하세요.
구성: 1) 시장 현황 요약 2) 핵심 인사이트 3가지 3) 경쟁사 분석 4) 전략적 제언 3가지
각 섹션은 제목(##)과 함께 상세하게 작성하세요.""",

    "🛍️ 상품 상세 설명": """다음 제품/키워드를 기반으로 네이버 스마트스토어에 최적화된 상품 상세 설명을 작성하세요.
구성: 1) 감성적 헤드라인 2) 제품 핵심 특징 5가지 (이모지 포함) 3) 사용 시나리오 4) 구매를 유도하는 CTA
네이버 검색 SEO를 고려해 키워드를 자연스럽게 포함하세요.""",

    "📱 SNS 카피": """다음 주제로 한국 소비자를 타겟으로 한 SNS 콘텐츠를 작성하세요.
[인스타그램 본문] — 감성적이고 트렌디하게, 해시태그 20개 포함
[블로그 포스팅 제목 5개 후보] — 클릭을 유도하는 SEO 최적화 제목
[카카오톡 채널 단문 메시지] — 50자 이내 임팩트 있는 문구 3개""",

    "📧 이메일/뉴스레터": """다음 주제로 전문적인 비즈니스 이메일/뉴스레터를 작성하세요.
구성: 1) 제목 (열람률 높은 주제줄 3개 후보) 2) 프리헤더 텍스트 3) 인사말 4) 본문 (핵심 내용 3단락) 5) CTA 버튼 문구 6) 서명
친근하면서도 전문적인 톤앤매너를 유지하세요.""",

    "📑 PPT 브로셔 스크립트": """다음 주제로 10~12장 분량의 PPT 브로셔 스크립트를 JSON 형식으로 작성하세요.
반드시 아래 형식만 출력하세요 (다른 설명 없이 JSON만):
[{"title": "슬라이드 제목", "points": ["내용 1", "내용 2", "내용 3"]}]""",
}


def gs_write(topic: str, context: str, content_type: str) -> str:
    """Claude API로 콘텐츠 생성"""
    if not REQUESTS_OK or not AI_API_KEY:
        return "❌ API 키가 설정되지 않았습니다. `.env` 파일을 확인하세요."

    sys_prompt = CONTENT_PROMPTS.get(content_type, CONTENT_PROMPTS["📊 마케팅 리포트"])
    user_msg = f"주제: {topic}\n\n[수집된 참고 데이터]\n{context[:6000]}"

    payload = {
        "model": "claude-3-5-sonnet",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}

    try:
        resp = requests.post(f"{AI_API_BASE}/chat/completions",
                             headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ AI 오류: {e}"


def gs_make_pptx(topic: str, slides_json: str) -> bytes | None:
    """JSON 슬라이드 스크립트 → .pptx bytes"""
    if not PPTX_OK:
        return None
    try:
        raw = slides_json
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        slides = json.loads(raw)
    except Exception:
        return None

    prs = Presentation()
    for slide_data in slides:
        sl = prs.slides.add_slide(prs.slide_layouts[1])
        sl.shapes.title.text = slide_data.get("title", "")
        tf = sl.placeholders[1].text_frame
        tf.word_wrap = True
        for point in slide_data.get("points", []):
            p = tf.add_paragraph()
            p.text = point
            p.font.size = Pt(18)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


st.divider()
tab_log, tab_work, tab_report, tab_genspark, tab_guide = st.tabs(
    ["📟 실시간 로그", "📝 작업 기록", "📈 순위 리포트", "✍️ AI 콘텐츠 작성", "❓ 사용법"]
)

with tab_log:
    col_r1, col_r2 = st.columns([1, 3])
    with col_r1:
        if st.button("🔄 새로고침", key="refresh_log"):
            st.rerun()
    with col_r2:
        auto_ref = st.checkbox("5초마다 자동 갱신", value=True, key="auto_ref")

    if auto_ref:
        import streamlit.components.v1 as components
        components.html("<script>setTimeout(()=>window.parent.location.reload(),5000);</script>", height=0)

    # system.log 표시
    log_content = read_log(SYSTEM_LOG_FILE, 50)
    st.markdown(f'<div class="log-box">{log_content}</div>', unsafe_allow_html=True)

with tab_work:
    # work_log.txt 표시
    work_content = read_log(WORK_LOG_FILE, 60)
    st.code(work_content, language="bash")

with tab_report:
    if os.path.exists(KEYWORD_LOG_FILE):
        try:
            df = pd.read_csv(KEYWORD_LOG_FILE, on_bad_lines="skip")
            st.dataframe(df.tail(30).iloc[::-1], use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"CSV 읽기 오류: {e}")
    elif os.path.exists("report.csv"):
        try:
            df = pd.read_csv("report.csv", on_bad_lines="skip")
            st.dataframe(df.tail(30).iloc[::-1], use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"report.csv 읽기 오류: {e}")
    else:
        st.info("작업 기록이 없습니다. 먼저 작업을 시작하세요.")

# ============================
# AI 콘텐츠 작성 탭
# ============================
with tab_genspark:
    st.header("✍️ GenSpark AI 콘텐츠 작성")
    st.caption("키워드를 입력하면 AI가 웹을 검색하고 마케팅 콘텐츠를 자동으로 작성합니다.")

    # ── 상태 초기화 ──
    if "gs_result" not in st.session_state:
        st.session_state.gs_result = ""
    if "gs_topic" not in st.session_state:
        st.session_state.gs_topic = ""

    # ── 입력 UI ──
    col_gs1, col_gs2 = st.columns([3, 1])
    with col_gs1:
        # 현재 선택된 키워드 자동 주입
        default_topic = selected_categories[0] if selected_categories else "나눔랩 코팅제"
        gs_topic = st.text_input(
            "🔍 주제 / 키워드",
            value=st.session_state.gs_topic or default_topic,
            placeholder="예: 듀라코트 리빙코트, 폴리실라잔 코팅제 시장 분석",
            key="gs_topic_input",
        )
    with col_gs2:
        gs_type = st.selectbox(
            "📋 콘텐츠 유형",
            list(CONTENT_PROMPTS.keys()),
            key="gs_type_sel",
        )

    col_gs_opt1, col_gs_opt2 = st.columns(2)
    with col_gs_opt1:
        use_web = st.checkbox("🌐 웹 검색 포함 (SerpAPI)", value=bool(SERPAPI_KEY), key="gs_use_web")
    with col_gs_opt2:
        extra_ctx = st.text_area(
            "📝 추가 참고 정보 (선택)",
            placeholder="제품 특징, 타겟 고객, 경쟁사 등 AI에게 알려줄 정보를 자유롭게 입력하세요.",
            height=80,
            key="gs_extra_ctx",
        )

    st.markdown("")
    btn_col1, btn_col2 = st.columns([2, 1])
    with btn_col1:
        run_gs = st.button("🚀 AI 콘텐츠 작성 시작", use_container_width=True, key="gs_run")
    with btn_col2:
        clear_gs = st.button("🗑️ 초기화", use_container_width=True, key="gs_clear")

    if clear_gs:
        st.session_state.gs_result = ""
        st.session_state.gs_topic = ""
        st.rerun()

    if run_gs and gs_topic.strip():
        st.session_state.gs_topic = gs_topic.strip()

        with st.spinner("🔍 웹 검색 중..."):
            context_parts = []
            if extra_ctx.strip():
                context_parts.append(f"[사용자 제공 정보]\n{extra_ctx.strip()}")
            if use_web:
                web_results = gs_search(gs_topic.strip(), num=5)
                for r in web_results:
                    context_parts.append(f"[출처: {r['url']}]\n{r['content']}")
                st.info(f"✅ 웹 검색 완료 — {len(web_results)}개 사이트 분석")
            else:
                st.info("📝 웹 검색 없이 AI 자체 지식으로 작성합니다.")
            context = "\n\n".join(context_parts)

        with st.spinner("🧠 Claude AI가 콘텐츠를 작성 중입니다..."):
            result = gs_write(gs_topic.strip(), context, gs_type)
            st.session_state.gs_result = result

    # ── 결과 표시 ──
    if st.session_state.gs_result:
        st.divider()
        result_text = st.session_state.gs_result

        st.markdown("### 📄 AI 작성 결과")
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:12px;'
            f'padding:20px;color:#e6edf3;line-height:1.8;font-size:14px;">',
            unsafe_allow_html=True,
        )
        st.markdown(result_text)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("")
        dl_col1, dl_col2, dl_col3 = st.columns(3)

        # Markdown 다운로드
        with dl_col1:
            fname_md = f"genspark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            st.download_button(
                "⬇️ Markdown 저장",
                data=result_text.encode("utf-8"),
                file_name=fname_md,
                mime="text/markdown",
                use_container_width=True,
                key="dl_md",
            )

        # TXT 다운로드
        with dl_col2:
            fname_txt = f"genspark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            st.download_button(
                "⬇️ TXT 저장",
                data=result_text.encode("utf-8"),
                file_name=fname_txt,
                mime="text/plain",
                use_container_width=True,
                key="dl_txt",
            )

        # PPT 다운로드 (PPT 유형일 때만)
        with dl_col3:
            if gs_type == "📑 PPT 브로셔 스크립트" and PPTX_OK:
                pptx_bytes = gs_make_pptx(st.session_state.gs_topic, result_text)
                if pptx_bytes:
                    fname_pptx = f"genspark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
                    st.download_button(
                        "⬇️ PPT 저장",
                        data=pptx_bytes,
                        file_name=fname_pptx,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                        key="dl_pptx",
                    )
                else:
                    st.warning("PPT 생성 실패 (JSON 형식 확인 필요)")
            elif not PPTX_OK:
                st.caption("PPT 저장: python-pptx 미설치")
            else:
                st.caption("PPT 저장: PPT 유형 선택 시 활성화")

    elif run_gs and not gs_topic.strip():
        st.error("주제/키워드를 입력하세요.")

    # ── 사용 팁 ──
    with st.expander("💡 GenSpark AI 콘텐츠 작성 사용 팁"):
        st.markdown("""
        | 콘텐츠 유형 | 최적 사용 시나리오 |
        |---|---|
        | 📊 마케팅 리포트 | 시장 조사, 경쟁사 분석, 전략 기획 |
        | 🛍️ 상품 상세 설명 | 스마트스토어 상품 등록 시 상세 페이지 |
        | 📱 SNS 카피 | 인스타그램/블로그 콘텐츠 발행 |
        | 📧 이메일/뉴스레터 | 고객 이메일 마케팅 캠페인 |
        | 📑 PPT 브로셔 | 제안서, 브로셔, 투자자 발표 자료 |

        **팁**: 왼쪽 키워드 목록에서 선택하면 주제가 자동으로 입력됩니다.
        **팁**: 추가 참고 정보란에 제품 특징을 입력하면 더 정확한 콘텐츠가 생성됩니다.
        """)


with tab_guide:
    st.markdown("""
    ### 🛡️ 사용 방법

    | 단계 | 설명 |
    |------|------|
    | 1️⃣ 키워드 선택 | 왼쪽에서 측정할 키워드를 체크 |
    | 2️⃣ 타겟 선택 | 사이드바에서 스마트스토어 상품 URL 선택 |
    | 3️⃣ 작업 시작 | **▶ 작업 시작** 버튼 클릭 |
    | 4️⃣ 로그 확인 | **📟 실시간 로그** 탭에서 진행상황 확인 |
    | 5️⃣ 결과 확인 | **📈 순위 리포트** 탭에서 결과 확인 |
    | 6️⃣ 중지 | **⏹ 작업 중지** 버튼으로 즉시 종료 |
    | 7️⃣ AI 작성 | **✍️ AI 콘텐츠 작성** 탭에서 마케팅 콘텐츠 자동 생성 |

    ### ⚠️ 주의사항
    - Google CSE API 키가 환경변수에 설정되어 있어야 합니다 (`GOOGLE_API_KEY`, `GOOGLE_CSE_ID`)
    - **📟 실시간 로그** 탭에서 각 키워드별 처리 현황을 실시간 확인 가능
    - **📝 작업 기록** 탭에서 `work_log.txt` 전체 이력 확인 가능
    - **✍️ AI 콘텐츠 작성** 탭: SerpAPI, Claude API 키가 `.env`에 설정되어야 합니다
    """)

st.caption("NanumLab Marketing Optimization Tool v4.0 — Developed by Antigravity")
