# -*- coding: utf-8 -*-
"""순위 발견 키워드만 traffic_config 생성 (filter_rank_keywords.py와 동기화)."""
from filter_rank_keywords import apply

if __name__ == "__main__":
    audit = apply()
    n = audit["summary"]["found_count"]
    print(f"Wrote {n} keyword_tasks (순위 추적·유지 전용)")
