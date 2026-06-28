# -*- coding: utf-8 -*-
"""순위 스캔·반영 — scan_and_apply_keyword_ranks.py 사용."""
from scan_and_apply_keyword_ranks import apply_scan, scan_all

if __name__ == "__main__":
    items = scan_all(use_cache=True)
    audit = apply_scan(items)
    print(audit["summary"])
