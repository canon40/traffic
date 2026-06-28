# -*- coding: utf-8 -*-
"""주간 순위 변동 리포트 (CLI)."""
from __future__ import annotations

import argparse
import sys

from rank_tracker import (
    build_weekly_rank_report,
    format_weekly_report_markdown,
    save_weekly_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="키워드 주간 순위 변동 리포트")
    parser.add_argument("--days", type=int, default=7, help="집계 기간(일), 기본 7")
    parser.add_argument("--save", action="store_true", help="JSON/CSV 저장")
    parser.add_argument("--markdown", action="store_true", help="마크다운 출력")
    args = parser.parse_args()

    report = build_weekly_rank_report(days=args.days)

    if args.markdown:
        print(format_weekly_report_markdown(report))
    else:
        print("=" * 60)
        print(f"주간 순위 리포트 ({report['period_start']} ~ {report['period_end']})")
        print(report["summary"])
        print("=" * 60)
        if not report["items"]:
            print("기간 내 기록이 없습니다. 순위 추적을 먼저 실행하세요.")
        for item in report["items"]:
            arrow = item["change_text"]
            print(
                f"  {item['keyword']:24s}  "
                f"{item['week_start_text']:>6s} → {item['week_end_text']:<6s}  "
                f"{arrow:>4s}  (최고 {item['best_text']}, {item['observations']}회)"
            )

    if args.save:
        json_path, csv_path = save_weekly_report(report)
        print(f"\n저장: {json_path}")
        print(f"저장: {csv_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
