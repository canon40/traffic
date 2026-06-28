# -*- coding: utf-8 -*-
"""트래픽 작업 결과 리포트 (CLI)."""
from __future__ import annotations

import argparse
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

from traffic_session_log import build_campaign_report, format_report_markdown, save_report


def main() -> int:
    parser = argparse.ArgumentParser(description="트래픽 작업·순위 결과 리포트")
    parser.add_argument("--days", type=int, default=30, help="집계 기간(일)")
    parser.add_argument("--save", action="store_true", help="JSON/MD 저장")
    parser.add_argument("--markdown", action="store_true", help="마크다운 출력")
    args = parser.parse_args()

    report = build_campaign_report(days=args.days)

    if args.markdown:
        print(format_report_markdown(report))
    else:
        print("=" * 70)
        print(f"트래픽 작업 결과 ({report['generated_at']})")
        print(report["summary"])
        print("=" * 70)
        if not report["items"]:
            print("기록 없음. 트래픽 캠페인 실행 후 다시 확인하세요.")
        for item in report["items"]:
            print(
                f"  [{item['campaign']}] {item['keyword']:22s} "
                f"{item['rank_start_text']:>6s} → {item['rank_end_text']:<6s} "
                f"{item['change_text']:>4s}  SERP {item['serp_best_text']:>6s}  "
                f"({item['sessions']}회) {item['result_status']}"
            )
            print(f"       {item['outcome']}")

    if args.save:
        json_path, md_path = save_report(report)
        print(f"\n저장: {json_path}")
        print(f"저장: {md_path}")
        print(f"세션 로그: traffic_sessions.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
