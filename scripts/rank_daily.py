# -*- coding: utf-8 -*-
"""Cloudtype / cron용 일일 순위 일괄 추적 (UI·스크립트 공용)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from daily_rank_track import main

if __name__ == "__main__":
    raise SystemExit(main())
