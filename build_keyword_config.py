# -*- coding: utf-8 -*-
"""traffic_config 생성 — scan_and_apply_keyword_ranks.py 로 위임."""
from scan_and_apply_keyword_ranks import apply_scan, scan_all

if __name__ == "__main__":
    items = scan_all(use_cache=True)
    audit = apply_scan(items, record_history=False)
    print(f"Wrote {audit['summary']['total']} keyword_tasks")
