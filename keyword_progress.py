# -*- coding: utf-8 -*-
"""키워드별 트래픽 작업 + 순위 진행 통합 보드."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from rank_tracker import NOT_FOUND_RANK, get_history, load_config
from traffic_session_log import build_campaign_report, load_all_sessions


def _rank_label(rank: int | None) -> str:
    if rank is None:
        return "-"
    if rank >= NOT_FOUND_RANK or rank < 0:
        return "미발견"
    return f"{rank}위"


def _latest_rank_by_keyword(history: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in history:
        kw = row.get("키워드", "")
        if not kw:
            continue
        try:
            rank = int(row.get("순위", NOT_FOUND_RANK))
        except (TypeError, ValueError):
            rank = NOT_FOUND_RANK
        latest[kw] = {
            "rank": rank,
            "date": row.get("날짜", ""),
            "detail": row.get("상세", ""),
            "change": row.get("변동", ""),
        }
    return latest


def _first_rank_in_period(history: list[dict], days: int) -> dict[str, int]:
    cutoff = datetime.now() - timedelta(days=days)
    first: dict[str, int] = {}
    for row in history:
        kw = row.get("키워드", "")
        try:
            dt = datetime.strptime(row.get("날짜", ""), "%Y-%m-%d %H:%M")
            rank = int(row.get("순위", NOT_FOUND_RANK))
        except (ValueError, TypeError):
            continue
        if dt < cutoff:
            continue
        if kw not in first:
            first[kw] = rank
    return first


def build_keyword_progress_board(days: int = 30) -> dict[str, Any]:
    config = load_config()
    keywords_cfg = config.get("keywords") or []
    history = get_history()
    latest = _latest_rank_by_keyword(history)
    first_in_period = _first_rank_in_period(history, days)

    traffic_report = build_campaign_report(days=days)
    traffic_by_kw: dict[str, dict] = {}
    for item in traffic_report.get("items", []):
        kw = item["keyword"]
        if kw not in traffic_by_kw or item.get("sessions", 0) >= traffic_by_kw[kw].get("sessions", 0):
            traffic_by_kw[kw] = item

    sessions_by_kw: dict[str, list] = defaultdict(list)
    for s in traffic_report.get("sessions", []):
        sessions_by_kw[s.get("keyword", "")].append(s)

    all_keywords: list[str] = []
    seen: set[str] = set()
    for item in keywords_cfg:
        kw = item.get("keyword", "")
        if kw and kw not in seen:
            all_keywords.append(kw)
            seen.add(kw)
    for kw in latest:
        if kw not in seen:
            all_keywords.append(kw)
            seen.add(kw)
    for kw in traffic_by_kw:
        if kw not in seen:
            all_keywords.append(kw)
            seen.add(kw)

    items = []
    counts = {"미진입": 0, "노출중": 0, "유지": 0, "상승": 0, "하락": 0, "SERP노출": 0}

    for kw in all_keywords:
        cur = latest.get(kw, {})
        cur_rank = cur.get("rank")
        start_rank = first_in_period.get(kw)
        if start_rank is None and cur_rank is not None:
            start_rank = cur_rank

        tr = traffic_by_kw.get(kw, {})
        serp_best = tr.get("serp_best")
        sessions = tr.get("sessions", 0) or len(sessions_by_kw.get(kw, []))

        change = None
        if start_rank is not None and cur_rank is not None:
            if start_rank < NOT_FOUND_RANK and cur_rank < NOT_FOUND_RANK:
                change = start_rank - cur_rank
            elif start_rank >= NOT_FOUND_RANK and cur_rank < NOT_FOUND_RANK:
                change = NOT_FOUND_RANK

        if cur_rank is not None and cur_rank < NOT_FOUND_RANK:
            if cur_rank <= 6:
                status = "유지"
                counts["유지"] += 1
            elif change and change > 0:
                status = "상승"
                counts["상승"] += 1
            elif change and change < 0:
                status = "하락"
                counts["하락"] += 1
            else:
                status = "노출중"
                counts["노출중"] += 1
        elif serp_best and serp_best < NOT_FOUND_RANK:
            status = "SERP노출"
            counts["SERP노출"] += 1
        else:
            status = "미진입"
            counts["미진입"] += 1

        items.append({
            "keyword": kw,
            "rank_start": start_rank,
            "rank_current": cur_rank,
            "rank_start_text": _rank_label(start_rank),
            "rank_current_text": _rank_label(cur_rank),
            "rank_change": change,
            "change_text": (
                f"▲{change}" if change and change > 0
                else f"▼{abs(change)}" if change and change < 0
                else "0" if change == 0
                else "-"
            ),
            "serp_best": serp_best,
            "serp_best_text": _rank_label(serp_best) if serp_best else "-",
            "traffic_sessions": sessions,
            "traffic_campaign": tr.get("campaign", ""),
            "traffic_outcome": tr.get("outcome", ""),
            "last_tracked": cur.get("date", ""),
            "status": status,
            "detail": cur.get("detail", ""),
        })

    def sort_key(x):
        order = {"유지": 0, "상승": 1, "노출중": 2, "SERP노출": 3, "하락": 4, "미진입": 5}
        r = x.get("rank_current")
        rank_val = r if r is not None and r < NOT_FOUND_RANK else (x.get("serp_best") or NOT_FOUND_RANK)
        return (order.get(x["status"], 9), rank_val)

    items.sort(key=sort_key)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period_days": days,
        "summary": (
            f"미진입 {counts['미진입']} · SERP노출 {counts['SERP노출']} · "
            f"노출 {counts['노출중']} · 상승 {counts['상승']} · 유지 {counts['유지']}"
        ),
        "counts": counts,
        "items": items,
    }
