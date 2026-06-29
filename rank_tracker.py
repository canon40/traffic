import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

from app_resources import get_storage_dir

HISTORY_HEADERS = ["날짜", "키워드", "스토어명", "순위", "이전순위", "변동", "작업유형", "상세"]
NOT_FOUND_RANK = 999


def _parse_history_dt(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except (TypeError, ValueError):
            continue
    return None


def _parse_rank(value) -> int | None:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    return rank


def rank_label(rank: int | None) -> str:
    if rank is None:
        return "기록 없음"
    if rank >= NOT_FOUND_RANK:
        return "미발견"
    return f"{rank}위"


def _rank_change_status(start_rank: int | None, end_rank: int | None) -> str:
    if start_rank is None or end_rank is None:
        return "기록부족"
    start_nf = start_rank >= NOT_FOUND_RANK
    end_nf = end_rank >= NOT_FOUND_RANK
    if start_nf and end_nf:
        return "미발견_유지"
    if start_nf and not end_nf:
        return "신규진입"
    if not start_nf and end_nf:
        return "이탈"
    delta = start_rank - end_rank
    if delta > 0:
        return "상승"
    if delta < 0:
        return "하락"
    return "유지"


def build_weekly_rank_report(days: int = 7) -> dict:
    """
    기간 내 키워드별 주간 순위 변화.
    - week_start_rank: 기간 직전 마지막 기록 (없으면 기간 내 첫 기록)
    - week_end_rank: 기간 내 마지막 기록
    """
    history = get_history()
    now = datetime.now()
    period_start = now - timedelta(days=days)

    if not history:
        return {
            "period_days": days,
            "period_start": period_start.strftime("%Y-%m-%d"),
            "period_end": now.strftime("%Y-%m-%d"),
            "generated_at": now.strftime("%Y-%m-%d %H:%M"),
            "summary": "순위 기록이 없습니다.",
            "items": [],
            "improved": 0,
            "declined": 0,
            "unchanged": 0,
            "entered": 0,
            "dropped": 0,
        }

    grouped: dict[tuple[str, str], list[tuple[datetime, dict]]] = defaultdict(list)
    for row in history:
        dt = _parse_history_dt(row.get("날짜", ""))
        if not dt:
            continue
        key = (row.get("키워드", ""), row.get("스토어명", ""))
        grouped[key].append((dt, row))

    items = []
    improved = declined = unchanged = entered = dropped = 0

    for (keyword, store_name), records in grouped.items():
        records.sort(key=lambda x: x[0])
        before = [(dt, row) for dt, row in records if dt < period_start]
        in_period = [(dt, row) for dt, row in records if dt >= period_start]
        if not in_period:
            continue

        if before:
            start_rank = _parse_rank(before[-1][1].get("순위"))
            start_at = before[-1][0].strftime("%Y-%m-%d %H:%M")
        else:
            start_rank = _parse_rank(in_period[0][1].get("순위"))
            start_at = in_period[0][0].strftime("%Y-%m-%d %H:%M")

        end_rank = _parse_rank(in_period[-1][1].get("순위"))
        end_at = in_period[-1][0].strftime("%Y-%m-%d %H:%M")

        period_ranks = [_parse_rank(row.get("순위")) for _, row in in_period]
        found_ranks = [r for r in period_ranks if r is not None and r < NOT_FOUND_RANK]
        best_rank = min(found_ranks) if found_ranks else None
        worst_rank = max(found_ranks) if found_ranks else None

        change = None
        if start_rank is not None and end_rank is not None:
            change = start_rank - end_rank

        status = _rank_change_status(start_rank, end_rank)
        if status == "상승":
            improved += 1
        elif status == "하락":
            declined += 1
        elif status == "신규진입":
            entered += 1
        elif status == "이탈":
            dropped += 1
        else:
            unchanged += 1

        if change is None:
            change_text = "-"
        elif change > 0:
            change_text = f"▲{change}"
        elif change < 0:
            change_text = f"▼{abs(change)}"
        else:
            change_text = "0"

        items.append({
            "keyword": keyword,
            "store_name": store_name,
            "week_start_rank": start_rank,
            "week_end_rank": end_rank,
            "week_start_text": rank_label(start_rank),
            "week_end_text": rank_label(end_rank),
            "change": change,
            "change_text": change_text,
            "status": status,
            "best_rank": best_rank,
            "worst_rank": worst_rank,
            "best_text": rank_label(best_rank),
            "observations": len(in_period),
            "start_at": start_at,
            "end_at": end_at,
        })

    items.sort(
        key=lambda x: (
            0 if x["status"] == "상승" else 1 if x["status"] == "신규진입" else 2,
            -(x["change"] or 0),
            x["week_end_rank"] if x["week_end_rank"] is not None else NOT_FOUND_RANK,
        )
    )

    summary = (
        f"최근 {days}일 - 상승 {improved}건, 하락 {declined}건, "
        f"신규진입 {entered}건, 이탈 {dropped}건, 유지/미발견 {unchanged}건"
    )

    return {
        "period_days": days,
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": now.strftime("%Y-%m-%d"),
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "items": items,
        "improved": improved,
        "declined": declined,
        "unchanged": unchanged,
        "entered": entered,
        "dropped": dropped,
    }


def format_weekly_report_markdown(report: dict) -> str:
    lines = [
        "### 📅 주간 순위 리포트",
        f"- 기간: {report.get('period_start')} ~ {report.get('period_end')} ({report.get('period_days')}일)",
        f"- 생성: {report.get('generated_at')}",
        f"- {report.get('summary')}",
        "",
        "| 키워드 | 주초 | 주말 | 변동 | 기간 최고 | 상태 |",
        "|--------|------|------|------|-----------|------|",
    ]
    for item in report.get("items", []):
        lines.append(
            f"| {item['keyword']} | {item['week_start_text']} | {item['week_end_text']} | "
            f"{item['change_text']} | {item['best_text']} | {item['status']} |"
        )
    if not report.get("items"):
        lines.append("| (기록 없음) | - | - | - | - | - |")
    return "\n".join(lines)


def save_weekly_report(report: dict, out_dir: str | os.PathLike | None = None) -> tuple[str, str]:
    base = Path(out_dir) if out_dir else Path(os.getcwd()) / "generated_content"
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / "weekly_rank_report.json"
    csv_path = base / "weekly_rank_report.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    headers = [
        "키워드", "스토어", "주초순위", "주말순위", "변동", "상태",
        "기간최고", "기간최저", "관측횟수", "주초시각", "주말시각",
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for item in report.get("items", []):
            writer.writerow([
                item["keyword"],
                item["store_name"],
                item["week_start_rank"] if item["week_start_rank"] is not None else "",
                item["week_end_rank"] if item["week_end_rank"] is not None else "",
                item["change_text"],
                item["status"],
                item["best_rank"] if item["best_rank"] is not None else "",
                item["worst_rank"] if item["worst_rank"] is not None else "",
                item["observations"],
                item["start_at"],
                item["end_at"],
            ])

    return str(json_path), str(csv_path)

# Android Chrome UA — 모바일 앱·실기기에서 네이버 응답 안정화
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
)


def _config_path():
    return os.path.join(get_storage_dir(), "config.json")


def _history_path():
    return os.path.join(get_storage_dir(), "rank_history.csv")


def _shopping_search_url(keyword, start=1):
    """네이버 모바일 쇼핑 검색 URL. start: 결과 시작 번호 (1, 41, 81, ...)"""
    return (
        f"https://m.search.naver.com/search.naver?"
        f"query={quote(keyword.strip())}&where=m_shop&start={start}"
    )


def _extract_ordered_product_ids(html):
    """스마트스토어 상품 ID 우선, 중복 제거 순서 유지."""
    ordered = []
    seen = set()

    def add(pid):
        if pid and pid not in seen:
            seen.add(pid)
            ordered.append(pid)

    # 1. smartstore URL matches (support both / and escaped \u002F)
    for pid in re.findall(r'smartstore\.naver\.com(?:/|\\u002F)[^\s"\'\\/]+(?:/|\\u002F)products(?:/|\\u002F)(\d+)', html):
        add(pid)
    # 2. Generic /products/ or \u002Fproducts\u002F matches
    for pid in re.findall(r'(?:/|\\u002F)products(?:/|\\u002F)(\d+)', html):
        add(pid)
    # 3. JSON channelProductId matches
    for pid in re.findall(r'["\']channelProductId["\']?\s*:\s*["\']?(\d+)["\']?', html):
        add(pid)
    # 4. nv_mid / nvMid fallback
    for pid in re.findall(r'[?&]nv_mid=(\d+)', html):
        add(pid)
    for pid in re.findall(r'nvMid["\']?\s*:\s*["\']?(\d+)', html):
        add(pid)
    return ordered



def test_naver_connection():
    """네이버 모바일 검색 연결 테스트."""
    try:
        res = requests.get(
            _shopping_search_url("퍼마코트"),
            headers={"User-Agent": MOBILE_UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=20,
        )
        if res.status_code != 200:
            return False, f"HTTP {res.status_code}"
        ids = _extract_ordered_product_ids(res.text)
        if not ids:
            return False, "검색 페이지는 열렸으나 상품 목록을 파싱하지 못했습니다."
        return True, f"연결 정상 (샘플 상품 {len(ids)}건 인식)"
    except Exception as e:
        return False, str(e)


def load_config():
    path = _config_path()
    if not os.path.exists(path):
        return {
            "store_name": "나눔랩",
            "track_interval_minutes": 60,
            "keywords": [],
            "product_urls": [],
            "blog_urls": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def ensure_history_file():
    path = _history_path()
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HISTORY_HEADERS)


def get_history(limit=None):
    ensure_history_file()
    rows = []
    try:
        with open(_history_path(), "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    if limit:
        return rows[-limit:]
    return rows


def get_last_rank(keyword, store_name):
    for row in reversed(get_history()):
        if row.get("키워드") == keyword and row.get("스토어명") == store_name:
            try:
                return int(row.get("순위", 100))
            except (TypeError, ValueError):
                return 100
    return None


def append_history(keyword, store_name, rank, prev_rank, task_type, detail):
    ensure_history_file()
    if prev_rank is None:
        change = "-"
    elif rank < prev_rank:
        change = f"+{prev_rank - rank}"
    elif rank > prev_rank:
        change = f"-{rank - prev_rank}"
    else:
        change = "0"

    with open(_history_path(), "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            keyword,
            store_name,
            rank,
            prev_rank if prev_rank is not None else "-",
            change,
            task_type,
            detail,
        ])


def get_all_product_rankings(keyword, product_map, logger=None, max_pages=13):
    """
    여러 페이지를 순회하며 product_map에 등록된 모든 상품의 노출 순위를 반환.
    product_map: { "상품ID": "상품명", ... }
    max_pages: 탐색할 최대 페이지 수 (기본 13 ≒ 520위)
    """
    import time

    def log(msg):
        if logger:
            logger(msg)

    keyword = keyword.strip()
    if not keyword:
        return [], "키워드를 입력하세요."
    if not product_map:
        return [], "등록 상품 DB가 비어 있습니다. 앱을 재설치하거나 products.json을 확인하세요."

    headers = {
        "User-Agent": MOBILE_UA,
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    remaining = set(product_map.keys())  # 아직 못 찾은 상품
    results = []
    cumulative_rank = 0

    try:
        for page in range(1, max_pages + 1):
            if not remaining:
                break  # 모든 상품 발견

            start = (page - 1) * 40 + 1
            url = _shopping_search_url(keyword, start=start)
            log(f"   📄 {page}페이지 조회 중... (start={start}, 미발견 상품 {len(remaining)}건)")

            try:
                res = requests.get(url, headers=headers, timeout=20)
                if res.status_code != 200:
                    log(f"   ⚠️ HTTP {res.status_code} — 중단")
                    break
            except requests.exceptions.Timeout:
                log(f"   ⚠️ {page}페이지 타임아웃 — 중단")
                break
            except requests.exceptions.ConnectionError:
                log(f"   ⚠️ {page}페이지 연결 실패 — 중단")
                break

            page_ids = _extract_ordered_product_ids(res.text)
            if not page_ids:
                log(f"   ⚠️ {page}페이지에서 상품 미발견 — 탐색 종료")
                break

            for pid in page_ids:
                cumulative_rank += 1
                if pid in remaining:
                    remaining.discard(pid)
                    results.append({
                        "id": pid,
                        "name": product_map[pid],
                        "rank": cumulative_rank,
                        "page": (cumulative_rank - 1) // 40 + 1,
                        "rank_in_page": ((cumulative_rank - 1) % 40) + 1,
                        "display": (
                            f"{cumulative_rank}위 "
                            f"({(cumulative_rank - 1) // 40 + 1}페이지 "
                            f"{((cumulative_rank - 1) % 40) + 1}번째)"
                        ),
                    })
                    append_history(
                        keyword,
                        product_map[pid],
                        cumulative_rank,
                        get_last_rank(keyword, product_map[pid]),
                        "순위진단",
                        f"{product_map[pid]} {cumulative_rank}위",
                    )
                    log(f"   ✅ {product_map[pid]}: {cumulative_rank}위")

            if page < max_pages and remaining:
                time.sleep(0.5)  # 네이버 요청 간격 준수

        # 탐색 범위 내 미발견 상품 처리
        for pid in remaining:
            log(f"   ❌ {product_map[pid]}: {cumulative_rank}위 이후 미발견")

        log(f"✅ '{keyword}' — 나눔랩 상품 {len(results)}건 매칭 (총 {cumulative_rank}위까지 탐색)")
        return results, None
    except Exception as e:
        return results, str(e)


def check_product_rank(keyword, product_id, logger=None, max_pages=13):
    """
    특정 스마트스토어 상품 ID의 쇼핑 검색 노출 순위.
    max_pages: 탐색할 최대 페이지 수 (1페이지=40개, 기본 13페이지 ≒ 520위까지)
    반환값: 실제 순위(int) 또는 None(조회 실패)
    찾지 못하면 max_pages*40 초과를 의미하는 큰 값 대신 None 반환.
    """
    def log(msg):
        if logger:
            logger(msg)

    product_id = str(product_id).strip()
    log(f"🔍 '{keyword}' 검색 결과에서 상품 {product_id} 순위 조회 (최대 {max_pages}페이지)...")
    headers = {
        "User-Agent": MOBILE_UA,
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.naver.com/",
    }

    cumulative_rank = 0  # 지금까지 세어온 상품 수

    try:
        for page in range(1, max_pages + 1):
            start = (page - 1) * 40 + 1
            url = _shopping_search_url(keyword, start=start)
            log(f"   📄 {page}페이지 조회 중... (start={start})")

            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 403:
                import time
                log("   ⚠️ HTTP 403 — 3초 후 1회 재시도")
                time.sleep(3)
                res = requests.get(url, headers=headers, timeout=20)
            if res.status_code != 200:
                log(f"   ⚠️ HTTP {res.status_code} — 중단")
                break

            page_ids = _extract_ordered_product_ids(res.text)
            if not page_ids:
                log(f"   ⚠️ {page}페이지에서 상품 미발견 — 탐색 종료")
                break

            for pid in page_ids:
                cumulative_rank += 1
                if pid == product_id:
                    log(f"✅ 상품 {product_id}: {cumulative_rank}위 ({page}페이지)")
                    return cumulative_rank

            import time
            time.sleep(0.5)  # 네이버 요청 간격 준수

        log(f"⚠️ 상품 {product_id} {cumulative_rank}위 이후에도 미발견")
        return None  # 탐색 범위 초과 — 순위 없음
    except Exception as e:
        log(f"❌ 상품 순위 조회 실패: {e}")
        return None


def check_naver_shopping_rank(keyword, store_name, logger=None):
    def log(msg):
        if logger:
            logger(msg)

    log(f"🔍 '{keyword}' 키워드로 '{store_name}' 순위 조회 중...")
    headers = {
        "User-Agent": MOBILE_UA,
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://m.naver.com/",
    }

    try:
        res = requests.get(_shopping_search_url(keyword), headers=headers, timeout=20)
        res.raise_for_status()
        text = res.text

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(text, "html.parser")
            items = soup.select(".lst_item") or soup.select("div[class*='product_item']")
            for idx, item in enumerate(items, 1):
                if store_name in item.get_text():
                    log(f"✅ {idx}위에서 '{store_name}' 발견")
                    return idx
        except Exception:
            matches = re.findall(
                r'<a[^>]*class="[^"]*product_link[^"]*"[^>]*>(.*?)</a>',
                text,
                re.DOTALL,
            )
            for idx, match in enumerate(matches, 1):
                if store_name in match:
                    log(f"✅ 정규식 파싱: {idx}위에서 '{store_name}' 발견")
                    return idx

        log("⚠️ 1페이지(약 100위) 내 미노출")
        return 100
    except Exception as e:
        log(f"❌ 순위 조회 실패: {e}")
        return None


def track_all_keywords(logger=None):
    config = load_config()
    keywords = config.get("keywords") or []
    if not keywords:
        kw = config.get("default_keyword")
        if kw:
            keywords = [{"keyword": kw, "store_name": config.get("store_name", "")}]
    if not keywords:
        if logger:
            logger("⚠️ 추적할 키워드가 없습니다. config.json을 설정하세요.")
        return []

    results = []
    import time as _time
    for idx, item in enumerate(keywords):
        keyword = item.get("keyword", "")
        store_name = item.get("store_name") or config.get("store_name", "")
        if not keyword or not store_name:
            continue

        if idx > 0:
            _time.sleep(2.0)

        prev = get_last_rank(keyword, store_name)
        product_id = item.get("product_id")
        if product_id:
            rank = check_product_rank(keyword, product_id, logger=logger)
        else:
            rank = check_naver_shopping_rank(keyword, store_name, logger=logger)
        if rank is None:
            # 탐색 범위 초과 — 미발견으로 기록
            detail = f"미발견 (520위 초과)" if prev is None else (
                f"{prev}위 → 미발견 (520위 초과)"
            )
            append_history(keyword, store_name, 999, prev, "순위추적", detail)
            results.append({
                "keyword": keyword,
                "store_name": store_name,
                "rank": None,
                "prev_rank": prev,
                "change": None,
                "detail": detail,
                "success": True,
                "not_found": True,
            })
            if logger:
                logger(f"📊 [{keyword}] {detail}")
            continue

        if prev is None:
            detail = f"첫 기록: {rank}위"
        elif rank < prev:
            detail = f"{prev}위 → {rank}위 ({prev - rank}단계 상승)"
        elif rank > prev:
            detail = f"{prev}위 → {rank}위 ({rank - prev}단계 하락)"
        else:
            detail = f"순위 유지 ({rank}위)"

        append_history(keyword, store_name, rank, prev, "순위추적", detail)
        results.append({
            "keyword": keyword,
            "store_name": store_name,
            "rank": rank,
            "prev_rank": prev,
            "change": prev - rank if prev is not None else 0,
            "detail": detail,
            "success": True,
            "not_found": False,
        })
        if logger:
            logger(f"📊 [{keyword}] {detail}")

    return results


def build_completion_report(results):
    if not results:
        return {
            "summary": "추적할 키워드가 없습니다.",
            "items": [],
            "improved": 0,
            "declined": 0,
            "unchanged": 0,
        }

    items = []
    improved = declined = unchanged = 0

    for r in results:
        if not r.get("success"):
            items.append({
                "keyword": r["keyword"],
                "status": "실패",
                "message": "순위 조회에 실패했습니다.",
            })
            continue

        prev = r.get("prev_rank")
        rank = r.get("rank")
        if rank is None:
            status = "미발견"
            unchanged += 1
        elif prev is None:
            status = "신규기록"
            unchanged += 1
        elif rank < prev:
            status = "상승"
            improved += 1
        elif rank > prev:
            status = "하락"
            declined += 1
        else:
            status = "유지"
            unchanged += 1

        rank_text = f"{rank}위" if rank is not None else "미발견"
        prev_text = f"{prev}위" if prev else "기록 없음"

        items.append({
            "keyword": r["keyword"],
            "store_name": r["store_name"],
            "status": status,
            "prev_rank": prev,
            "current_rank": rank,
            "prev_text": prev_text,
            "rank_text": rank_text,
            "detail": r.get("detail", ""),
            "tasks": ["네이버 쇼핑 모바일 검색 순위 조회"],
        })

    lines = []
    for item in items:
        if item["status"] == "실패":
            lines.append(f"• {item['keyword']}: 조회 실패")
        else:
            lines.append(f"• {item['keyword']}: {item['prev_text']} → {item['rank_text']} ({item['status']})")

    summary = (
        f"작업 완료 — 상승 {improved}건, 하락 {declined}건, "
        f"유지/신규 {unchanged + (len(items) - improved - declined - sum(1 for i in items if i['status']=='실패'))}건"
    )

    return {
        "summary": summary,
        "items": items,
        "improved": improved,
        "declined": declined,
        "unchanged": unchanged,
        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
