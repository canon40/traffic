# -*- coding: utf-8 -*-
"""
순서대로 작업 파이프라인:
  1) 트래픽 캠페인 상태 확인
  2) SEO 붙여넣기 가이드·블로그 초안 생성
  3) SEO 점검 (현재 vs 권장)
  4) 순위 추적 (전체 키워드)
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_PATH = ROOT / "generated_content" / "workflow_report.json"
PY = r"C:\Users\hymin\AppData\Local\Python\bin\python.exe"


def step1_campaign_status() -> dict:
    log = ROOT / "fast_entry_run.log"
    session_log = ROOT / "fast_entry_log.jsonl"
    status = {
        "step": 1,
        "name": "트래픽 캠페인",
        "running": False,
        "progress": None,
        "completed_sessions": 0,
        "errors_429": 0,
        "note": "",
    }
    if log.exists():
        text = log.read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"\[(\d+)/(\d+)\]", text)
        if m:
            cur, total = m[-1]
            status["progress"] = f"{cur}/{total}"
            status["running"] = int(cur) < int(total)
        status["errors_429"] = text.count("HTTP 429")
        status["completed_sessions"] = len(
            [ln for ln in text.splitlines() if "→ TARGET_FOUND" in ln or "→ ERROR" in ln or "→ FALLBACK" in ln]
        )
    if session_log.exists():
        status["completed_sessions"] = max(
            status["completed_sessions"],
            sum(1 for _ in session_log.open(encoding="utf-8")),
        )
    if status["errors_429"] >= 3:
        status["note"] = "429 다발 — 세션 간격을 늘리거나 캠페인 일시 중지 권장"
    elif status["running"]:
        status["note"] = "백그라운드 캠페인 진행 중 — SEO·순위 작업 병행 가능"
    else:
        status["note"] = "캠페인 미실행 또는 완료"
    return status


def step2_seo_generate() -> dict:
    from seo_fixes import run as seo_run

    manifest = seo_run()
    return {
        "step": 2,
        "name": "SEO 가이드 생성",
        "guide": manifest["guide_path"],
        "drafts": manifest["blog_drafts"],
        "ok": True,
    }


def step3_seo_audit() -> dict:
    from seo_checker import run_full_audit

    def _log(msg):
        print(msg)

    results = run_full_audit(logger=_log)
    summary = results.get("summary", {})
    recs = summary.get("recommendations", [])
    return {
        "step": 3,
        "name": "SEO 점검",
        "average_score": summary.get("average_score"),
        "pages": summary.get("total_pages"),
        "recommendations": recs,
        "ok": True,
    }


def step4_rank_track() -> dict:
    from rank_tracker import build_completion_report, track_all_keywords

    def _log(msg):
        print(msg)

    print("\n[4/4] 순위 추적 시작 (키워드 수에 따라 수 분 소요)...")
    results = track_all_keywords(logger=_log)
    report = build_completion_report(results)
    return {
        "step": 4,
        "name": "순위 추적",
        "summary": report.get("summary"),
        "improved": report.get("improved"),
        "declined": report.get("declined"),
        "items": report.get("items", [])[:20],
        "total_keywords": len(results),
        "ok": True,
    }


def main() -> int:
    print("=" * 60)
    print("나눔랩 작업 파이프라인 (순서대로)")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    report = {"started_at": datetime.now().isoformat(), "steps": []}

    print("\n[1/4] 트래픽 캠페인 상태 확인...")
    s1 = step1_campaign_status()
    report["steps"].append(s1)
    print(f"  진행: {s1.get('progress') or '-'} | 429 오류: {s1['errors_429']}회")
    print(f"  → {s1['note']}")

    print("\n[2/4] SEO 붙여넣기 가이드·블로그 초안 생성...")
    s2 = step2_seo_generate()
    report["steps"].append(s2)
    print(f"  가이드: {s2['guide']}")

    print("\n[3/4] SEO 점검...")
    s3 = step3_seo_audit()
    report["steps"].append(s3)
    print(f"  평균 점수: {s3.get('average_score')}점 / {s3.get('pages')}페이지")
    for r in s3.get("recommendations", [])[:8]:
        print(f"  • {r}")

    s4 = step4_rank_track()
    report["steps"].append(s4)
    print(f"\n  {s4.get('summary')}")

    report["finished_at"] = datetime.now().isoformat()
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n리포트 저장: {REPORT_PATH}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
