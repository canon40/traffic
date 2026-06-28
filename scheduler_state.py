# -*- coding: utf-8 -*-
"""스케줄 작업 마지막 실행 시각 기록."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".scheduler_state.json"


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def mark_success(task: str, detail: str = "") -> None:
    state = load_state()
    state[task] = {
        "last_success": datetime.now().isoformat(),
        "detail": detail,
    }
    save_state(state)


def last_success_date(task: str):
    state = load_state()
    entry = state.get(task, {})
    raw = entry.get("last_success")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def is_done_today(task: str) -> bool:
    last = last_success_date(task)
    if not last:
        return False
    return last >= datetime.now().date()
