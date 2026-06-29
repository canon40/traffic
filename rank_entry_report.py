# -*- coding: utf-8 -*-
"""검색어 순위 진입 현황 요약 — 100위/TOP10/TOP50/미진입."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rank_tracker import NOT_FOUND_RANK

ROOT = Path(__file__).resolve().parent
SCAN_FILE = ROOT / "generated_content" / "keyword_rank_scan.json"
# 180개 전체 스캔 결과는 이 경로에 저장하면 우선 사용
FULL_SCAN_FILE = ROOT / "generated_content" / "keyword_rank_full.json"
CATALOG_FILE = ROOT / "data" / "keyword_catalog.json"
TXT_OUT = ROOT / "generated_content" / "rank_report_latest.txt"
JSON_OUT = ROOT / "data" / "rank_latest_summary.json"
ENTRY_MAX = 100


def _norm_rank(rank: int | None) -> int | None:
    if rank is None or rank >= NOT_FOUND_RANK or rank <= 0:
        return None
    return rank


def _load_items() -> list[dict]:
    for path in (FULL_SCAN_FILE, SCAN_FILE):
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("items") or []
            if items:
                return items
    if CATALOG_FILE.exists():
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    return []


def build_entry_summary(items: list[dict] | None = None) -> dict[str, Any]:
    items = items if items is not None else _load_items()
    rows: list[dict] = []
    for it in items:
        rank = _norm_rank(it.get("rank"))
        rows.append(
            {
                "keyword": it.get("keyword", ""),
                "product_id": it.get("product_id", ""),
                "product_url": it.get("product_url", ""),
                "rank": rank,
                "rank_text": f"{rank}위" if rank else "미진입",
                "zone": it.get("zone", ""),
            }
        )

    rows.sort(key=lambda x: (x["rank"] is None, x["rank"] or 9999, x["keyword"]))

    total = len(rows)
    in_100 = [r for r in rows if r["rank"] and r["rank"] <= ENTRY_MAX]
    top10 = [r for r in rows if r["rank"] and r["rank"] <= 10]
    top50 = [r for r in rows if r["rank"] and r["rank"] <= 50]
    not_entered = [r for r in rows if not r["rank"] or r["rank"] > ENTRY_MAX]

    pct = round(len(in_100) / total * 100, 1) if total else 0.0

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "entered_100": len(in_100),
        "entered_100_pct": pct,
        "top10": len(top10),
        "top50": len(top50),
        "not_entered": len(not_entered),
        "entry_max": ENTRY_MAX,
        "in_100_keywords": in_100,
        "top10_keywords": top10,
        "not_entered_keywords": not_entered,
        "all": rows,
    }


def format_text_report(summary: dict[str, Any]) -> str:
    lines = [
        "=" * 56,
        f"  순위 진입 현황  ({summary['generated_at']})",
        "=" * 56,
        f"  전체 키워드     : {summary['total']}개",
        f"  100위 이내(진입): {summary['entered_100']}개 ({summary['entered_100_pct']}%)",
        f"  TOP 10          : {summary['top10']}개",
        f"  TOP 50          : {summary['top50']}개",
        f"  미진입(작업대상): {summary['not_entered']}개",
        "",
        "── 100위 이내 키워드 ──",
    ]
    for r in summary.get("in_100_keywords", []):
        lines.append(f"  {r['rank']:>3}위  {r['keyword']}")
    lines.append("")
    lines.append("── 미진입 (일부) ──")
    for r in summary.get("not_entered_keywords", [])[:40]:
        lines.append(f"  ---   {r['keyword']}")
    if summary["not_entered"] > 40:
        lines.append(f"  ... 외 {summary['not_entered'] - 40}개")
    lines.append("")
    return "\n".join(lines)


def write_reports(summary: dict[str, Any] | None = None) -> dict[str, Any]:
    summary = summary or build_entry_summary()
    TXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    TXT_OUT.write_text(format_text_report(summary), encoding="utf-8")
    JSON_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def print_progress(summary: dict[str, Any] | None = None) -> None:
    summary = summary or build_entry_summary()
    print(format_text_report(summary))


def not_entered_keywords(summary: dict[str, Any] | None = None) -> list[str]:
    summary = summary or build_entry_summary()
    return [r["keyword"] for r in summary.get("not_entered_keywords", []) if r.get("keyword")]


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="순위 진입 현황 리포트")
    p.add_argument("--write", action="store_true", help="txt/json 저장")
    p.add_argument("--print", dest="do_print", action="store_true", help="터미널 출력")
    args = p.parse_args()

    summary = build_entry_summary()
    if args.write:
        write_reports(summary)
        print(f"저장: {TXT_OUT}")
        print(f"저장: {JSON_OUT}")
    if args.do_print or not args.write:
        print_progress(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
