# -*- coding: utf-8 -*-
"""API 키·순위 조회·Cloudtype 설정 점검."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from env_loader import api_keys_status, load_env


def main() -> int:
    load_env()
    keys = api_keys_status()
    print("=== API 키 상태 ===")
    print(json.dumps(keys, ensure_ascii=False, indent=2))

    if not keys["naver_open_api"] and not keys["serpapi"]:
        print("\n⚠️ NAVER_CLIENT_ID+SECRET 또는 SERPAPI_KEY가 필요합니다.")
        print("   전체 순위(1000위): https://developers.naver.com 에서 쇼핑 검색 API 발급")
        return 1

    from rank_api_provider import check_product_rank_api

    tests = [
        ("퍼마코트 자동차 코팅제", "12639296730"),
        ("듀라코트 리빙코트", "10713170202"),
        ("리빙코트", "10713170202"),
    ]
    print("\n=== 샘플 순위 테스트 ===")
    for kw, pid in tests:
        rank = check_product_rank_api(kw, pid, max_pages=10, logger=print)
        label = f"{rank}위" if rank else "미발견"
        print(f"→ {kw}: {label}\n")

    print("=== Cloudtype 환경변수 (대시보드에 동일하게 설정) ===")
    for name in (
        "NAVER_CLIENT_ID",
        "NAVER_CLIENT_SECRET",
        "SERPAPI_KEY",
        "RANK_USE_API=1",
        "ENABLE_CLOUD_RANK_SWEEP=1",
        "AUTO_START_BACKGROUND=1",
        "GCS_BUCKET",
        "CRON_SECRET",
    ):
        if "=" in name:
            print(f"  {name}")
        else:
            val = __import__("os").environ.get(name, "")
            print(f"  {name}={'(설정됨)' if val else '(미설정)'}")

    print("\n배포 후 확인: https://<서비스URL>/api/cloud/status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
