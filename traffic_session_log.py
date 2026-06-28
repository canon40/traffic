# -*- coding: utf-8 -*-
"""트래픽 세션 통합 로그 + 순위 전후 추적."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SESSION_LOG_JSONL = ROOT / "traffic_sessions.jsonl"
SESSION_LOG_CSV = ROOT / "traffic_sessions.csv"
CSV_HEADERS = [
    "날짜",
    "캠페인",
    "키워드",
    "상품ID",
    "모드",
    "작업내용",
    "SERP순위",
    "작업전순위",
    "작업후순위",
    "순위변동",
    "체류초",
    "타겟발견",
    "상태",
    "결과요약",
]

NOT_FOUND = 999


def _product_id(url: str) -> str:
    return url.rstrip("/").split("/")[-1] if url else ""


def rank_text(rank: int | None) -> str:
    if rank is None:
        return "-"
    if rank >= NOT_FOUND or rank < 0:
        return "미발견"
    return f"{rank}위"


def rank_delta(before: int | None, after: int | None) -> int | None:
    if before is None or after is None:
        return None
    if before >= NOT_FOUND and after >= NOT_FOUND:
        return 0
    if before >= NOT_FOUND:
        return None
    if after >= NOT_FOUND:
        return -(NOT_FOUND - before)
    return before - after


def outcome_summary(
    *,
    status: str,
    rank_before: int | None,
    rank_after: int | None,
    serp_rank: int | None,
    target_found: bool,
) -> str:
    delta = rank_delta(rank_before, rank_after)
    parts: list[str] = []

    if delta is not None and delta > 0:
        parts.append(f"순위 {rank_text(rank_before)}→{rank_text(rank_after)} (▲{delta})")
    elif delta is not None and delta < 0:
        parts.append(f"순위 {rank_text(rank_before)}→{rank_text(rank_after)} (▼{abs(delta)})")
    elif rank_before is not None and rank_after is not None:
        parts.append(f"순위 {rank_text(rank_after)} 유지")

    if serp_rank and serp_rank < NOT_FOUND:
        parts.append(f"SERP {serp_rank}위 노출")
    elif target_found:
        parts.append("SERP에서 타겟 클릭")
    elif status.startswith("ERROR"):
        parts.append("오류/차단")
    else:
        parts.append("SERP 미노출·직접유입")

    return " · ".join(parts) if parts else status


def _ensure_csv() -> None:
    if SESSION_LOG_CSV.exists():
        return
    with SESSION_LOG_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow(CSV_HEADERS)


def append_session(record: dict[str, Any]) -> None:
    with SESSION_LOG_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    _ensure_csv()
    delta = record.get("rank_change")
    delta_text = "-"
    if delta is not None:
        if delta > 0:
            delta_text = f"▲{delta}"
        elif delta < 0:
            delta_text = f"▼{abs(delta)}"
        else:
            delta_text = "0"

    with SESSION_LOG_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow([
            record.get("at", "")[:16].replace("T", " "),
            record.get("campaign", ""),
            record.get("keyword", ""),
            record.get("product_id", ""),
            record.get("mode", ""),
            record.get("work_summary", ""),
            record.get("serp_rank") if record.get("serp_rank") else "",
            rank_text(record.get("rank_before")),
            rank_text(record.get("rank_after")),
            delta_text,
            record.get("dwell_seconds", ""),
            "Y" if record.get("target_found") else "N",
            record.get("status", ""),
            record.get("outcome", ""),
        ])


def check_rank_api(keyword: str, product_id: str) -> int | None:
    if not product_id:
        return None
    try:
        from rank_tracker import check_product_rank

        r = check_product_rank(keyword, product_id)
        return r if r is not None else NOT_FOUND
    except Exception:
        return None


def run_tracked_session(
    *,
    campaign: str,
    keyword: str,
    product_url: str = "",
    mode: str = "",
    track_rank: bool = False,
    rank_before: int | None = None,
    target_store_id: str = "nanumlab",
    target_urls: list[str] | None = None,
    headless: bool = False,
    stay_range: tuple[int, int] = (30, 90),
    **kwargs: Any,
) -> dict[str, Any]:
    from traffic_service import run_session

    product_id = _product_id(product_url)
    if track_rank and rank_before is None and product_id:
        rank_before = check_rank_api(keyword, product_id)

    result = run_session(
        keyword=keyword,
        target_store_id=target_store_id,
        target_urls=target_urls or [],
        headless=headless,
        stay_range=stay_range,
        preferred_url=product_url,
    )

    rank_after = None
    if track_rank and product_id:
        rank_after = check_rank_api(keyword, product_id)

    detected = bool(result.get("detected"))
    if result.get("target_found"):
        status = "TARGET_FOUND"
    elif detected:
        status = f"DETECTED: {result.get('error', '')}"
    elif result.get("error"):
        status = f"ERROR: {result.get('error')}"
    else:
        status = "FALLBACK"

    trace = result.get("state_trace") or []
    work_bits = []
    if "WARMUP" in trace:
        work_bits.append("웜업")
    if "BLOG_SEARCH" in trace:
        work_bits.append("블로그검색")
    if "SEARCH" in trace:
        work_bits.append("쇼핑검색")
    if "SERP_BROWSE" in trace:
        work_bits.append("SERP탐색")
    if "TARGET_VISIT" in trace:
        work_bits.append("상품체류")

    change = rank_delta(rank_before, rank_after)
    record = {
        "at": datetime.now().isoformat(),
        "campaign": campaign,
        "keyword": keyword,
        "product_id": product_id,
        "product_url": product_url,
        "mode": mode,
        "work_summary": " → ".join(work_bits),
        "state_trace": trace,
        "serp_rank": result.get("serp_rank"),
        "rank_before": rank_before,
        "rank_after": rank_after,
        "rank_change": change,
        "dwell_seconds": result.get("dwell_seconds"),
        "target_found": result.get("target_found"),
        "detected": detected,
        "status": status,
        "outcome": outcome_summary(
            status=status,
            rank_before=rank_before,
            rank_after=rank_after,
            serp_rank=result.get("serp_rank"),
            target_found=bool(result.get("target_found")),
        ),
    }
    append_session(record)
    return {**result, "session_record": record, "status": status}


def load_all_sessions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def ingest(path: Path, campaign: str, mapper) -> None:
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    rows.append(mapper(raw, campaign))
                except json.JSONDecodeError:
                    continue

    ingest(
        SESSION_LOG_JSONL,
        "",
        lambda r, c: {**r, "campaign": r.get("campaign") or c, "source": "traffic_sessions"},
    )
    ingest(
        ROOT / "fast_entry_log.jsonl",
        "fast_entry",
        lambda r, c: {
            "at": r.get("at", ""),
            "campaign": c,
            "keyword": r.get("keyword", ""),
            "mode": r.get("mode", ""),
            "status": r.get("status", ""),
            "target_found": r.get("target_found"),
            "detected": r.get("detected"),
            "work_summary": "쇼핑검색→SERP→상품체류",
            "source": "legacy_fast_entry",
        },
    )
    ingest(
        ROOT / "focus_campaign_log.jsonl",
        "focus",
        lambda r, c: {
            "at": r.get("at", ""),
            "campaign": c,
            "keyword": r.get("keyword", ""),
            "mode": r.get("zone", ""),
            "status": r.get("status", ""),
            "serp_rank": r.get("observed_rank"),
            "detected": r.get("detected"),
            "work_summary": "후보권 집중 트래픽",
            "source": "legacy_focus",
        },
    )

    rows.sort(key=lambda x: x.get("at", ""))
    return rows


def build_campaign_report(days: int = 30) -> dict[str, Any]:
    from datetime import timedelta

    from rank_tracker import get_history

    sessions = load_all_sessions()
    cutoff = datetime.now() - timedelta(days=days)
    filtered = []
    for s in sessions:
        at = s.get("at", "")
        try:
            dt = datetime.fromisoformat(at.replace("Z", ""))
        except ValueError:
            continue
        if dt >= cutoff:
            filtered.append({**s, "_dt": dt})
    sessions = filtered

    history = get_history()
    hist_by_kw: dict[str, list[tuple[datetime, int]]] = {}
    for row in history:
        kw = row.get("키워드", "")
        try:
            dt = datetime.strptime(row.get("날짜", ""), "%Y-%m-%d %H:%M")
            rank = int(row.get("순위", NOT_FOUND))
        except (ValueError, TypeError):
            continue
        hist_by_kw.setdefault(kw, []).append((dt, rank))
    for kw in hist_by_kw:
        hist_by_kw[kw].sort()

    def hist_rank_at(kw: str, dt: datetime, direction: str) -> int | None:
        rows = hist_by_kw.get(kw, [])
        if not rows:
            return None
        if direction == "before":
            prior = [r for t, r in rows if t <= dt]
            return prior[-1] if prior else None
        after = [r for t, r in rows if t >= dt]
        return after[0] if after else None

    groups: dict[tuple[str, str], list[dict]] = {}
    for s in sessions:
        key = (s.get("campaign", "unknown"), s.get("keyword", ""))
        groups.setdefault(key, []).append(s)

    items = []
    for (campaign, keyword), group in sorted(groups.items(), key=lambda x: x[0]):
        group.sort(key=lambda x: x.get("at", ""))
        first, last = group[0], group[-1]
        dt_first = first.get("_dt")
        dt_last = last.get("_dt")

        rank_start = first.get("rank_before")
        rank_end = last.get("rank_after")
        if rank_start is None and dt_first:
            rank_start = hist_rank_at(keyword, dt_first, "before")
        if rank_end is None and dt_last:
            rank_end = hist_rank_at(keyword, dt_last, "after")

        serp_ranks = [
            int(s["serp_rank"])
            for s in group
            if s.get("serp_rank") and int(s["serp_rank"]) < NOT_FOUND
        ]
        serp_best = min(serp_ranks) if serp_ranks else None

        found_cnt = sum(1 for s in group if s.get("target_found"))
        error_cnt = sum(1 for s in group if str(s.get("status", "")).startswith(("ERROR", "DETECTED")))
        change = rank_delta(rank_start, rank_end)

        if change is not None and change > 0:
            result_status = "순위상승"
        elif change is not None and change < 0:
            result_status = "순위하락"
        elif serp_best and serp_best <= 100:
            result_status = "SERP노출"
        elif found_cnt > 0:
            result_status = "타겟클릭"
        elif error_cnt == len(group):
            result_status = "차단/오류"
        else:
            result_status = "진행중"

        items.append({
            "campaign": campaign,
            "keyword": keyword,
            "sessions": len(group),
            "rank_start": rank_start,
            "rank_end": rank_end,
            "rank_start_text": rank_text(rank_start),
            "rank_end_text": rank_text(rank_end),
            "rank_change": change,
            "change_text": (
                f"▲{change}" if change and change > 0
                else f"▼{abs(change)}" if change and change < 0
                else "0" if change == 0
                else "-"
            ),
            "serp_best": serp_best,
            "serp_best_text": rank_text(serp_best) if serp_best else "-",
            "target_found_sessions": found_cnt,
            "error_sessions": error_cnt,
            "result_status": result_status,
            "period_start": first.get("at", "")[:16],
            "period_end": last.get("at", "")[:16],
            "outcome": outcome_summary(
                status=last.get("status", ""),
                rank_before=rank_start,
                rank_after=rank_end,
                serp_rank=serp_best,
                target_found=found_cnt > 0,
            ),
        })

    items.sort(
        key=lambda x: (
            0 if x["result_status"] == "순위상승" else 1,
            -(x["rank_change"] or 0),
            x["serp_best"] if x["serp_best"] else NOT_FOUND,
        )
    )

    improved = sum(1 for i in items if i.get("rank_change") and i["rank_change"] > 0)
    declined = sum(1 for i in items if i.get("rank_change") and i["rank_change"] < 0)

    return {
        "period_days": days,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_sessions": len(sessions),
        "keyword_count": len(items),
        "improved": improved,
        "declined": declined,
        "summary": (
            f"최근 {days}일 트래픽 {len(sessions)}세션 / {len(items)}키워드 · "
            f"순위상승 {improved} · 하락 {declined}"
        ),
        "items": items,
        "sessions": sessions,
    }


def format_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "### 트래픽 작업 결과 리포트",
        f"- 생성: {report.get('generated_at')}",
        f"- {report.get('summary')}",
        "",
        "| 캠페인 | 키워드 | 세션 | 작업전 | 작업후 | 변동 | SERP최고 | 결과 |",
        "|--------|--------|------|--------|--------|------|----------|------|",
    ]
    for item in report.get("items", []):
        lines.append(
            f"| {item['campaign']} | {item['keyword']} | {item['sessions']} | "
            f"{item['rank_start_text']} | {item['rank_end_text']} | {item['change_text']} | "
            f"{item['serp_best_text']} | {item['result_status']} |"
        )
    if not report.get("items"):
        lines.append("| - | - | - | - | - | - | - | - |")
    return "\n".join(lines)


def save_report(report: dict[str, Any]) -> tuple[str, str]:
    out = ROOT / "generated_content"
    out.mkdir(exist_ok=True)
    json_path = out / "traffic_campaign_report.json"
    md_path = out / "traffic_campaign_report.md"

    export = {k: v for k, v in report.items() if k != "sessions"}
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(format_report_markdown(report))

    return str(json_path), str(md_path)
