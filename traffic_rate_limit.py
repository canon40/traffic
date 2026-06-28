# -*- coding: utf-8 -*-
"""
스마트스토어 HTTP 429 완화 — 세션 간격·시간당 한도·429 누적 쿨다운.
상태 파일: .traffic_rate_state.json
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / ".traffic_rate_state.json"

DEFAULTS = {
    "min_session_gap_sec": 120,
    "max_sessions_per_hour": 15,
    "cooldown_429_sec": 45 * 60,
    "cooldown_429_escalated_sec": 90 * 60,
    "escalate_after_consecutive_429": 3,
    "batch_size": 10,
    "batch_rest_sec": 20 * 60,
}


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_rate_config(cfg: dict | None = None) -> dict[str, Any]:
    merged = dict(DEFAULTS)
    if cfg:
        merged.update(cfg.get("rate_limit") or {})
    return merged


def get_state() -> dict[str, Any]:
    s = _load_state()
    now = time.time()
    return {
        "last_session_at": s.get("last_session_at", 0),
        "hour_start": s.get("hour_start", now),
        "sessions_this_hour": s.get("sessions_this_hour", 0),
        "consecutive_429": s.get("consecutive_429", 0),
        "blocked_until": s.get("blocked_until", 0),
        "sessions_since_rest": s.get("sessions_since_rest", 0),
        "total_429": s.get("total_429", 0),
    }


def record_session_start() -> None:
    now = time.time()
    s = _load_state()
    hour_start = s.get("hour_start", now)
    if now - hour_start > 3600:
        hour_start = now
        sessions_hour = 0
    else:
        sessions_hour = s.get("sessions_this_hour", 0)

    s.update({
        "last_session_at": now,
        "hour_start": hour_start,
        "sessions_this_hour": sessions_hour + 1,
        "sessions_since_rest": s.get("sessions_since_rest", 0) + 1,
    })
    _save_state(s)


def record_429() -> int:
    """429 발생 기록. 권장 대기 초 반환."""
    now = time.time()
    s = _load_state()
    cfg = load_rate_config()
    consecutive = s.get("consecutive_429", 0) + 1
    total = s.get("total_429", 0) + 1

    if consecutive >= cfg["escalate_after_consecutive_429"]:
        cooldown = cfg["cooldown_429_escalated_sec"]
    else:
        cooldown = cfg["cooldown_429_sec"]

    jitter = random.uniform(0.9, 1.15)
    wait_sec = int(cooldown * jitter)
    blocked_until = now + wait_sec

    s.update({
        "consecutive_429": consecutive,
        "total_429": total,
        "blocked_until": blocked_until,
        "last_429_at": now,
    })
    _save_state(s)
    return wait_sec


def record_success() -> None:
    """정상 세션 완료 시 연속 429 카운터 리셋."""
    s = _load_state()
    if s.get("consecutive_429", 0) == 0:
        return
    s["consecutive_429"] = 0
    _save_state(s)


def record_batch_rest(cfg: dict | None = None) -> None:
    s = _load_state()
    s["sessions_since_rest"] = 0
    _save_state(s)


def wait_seconds_before_session(cfg: dict | None = None) -> tuple[int, str]:
    """
    다음 세션 전 대기 시간(초)과 사유 반환. 0이면 즉시 진행 가능.
    호출 측에서 time.sleep(wait) 수행.
    """
    limits = load_rate_config(cfg)
    state = get_state()
    now = time.time()
    reasons: list[tuple[int, str]] = []

    blocked_until = state["blocked_until"]
    if blocked_until > now:
        reasons.append((
            int(blocked_until - now),
            f"429 쿨다운 (~{datetime.fromtimestamp(blocked_until).strftime('%H:%M')}까지)",
        ))

    gap = limits["min_session_gap_sec"]
    last = state["last_session_at"]
    if last > 0:
        elapsed = now - last
        if elapsed < gap:
            reasons.append((int(gap - elapsed), f"최소 간격 {gap}초"))

    hour_start = state["hour_start"]
    if now - hour_start > 3600:
        sessions_hour = 0
    else:
        sessions_hour = state["sessions_this_hour"]

    max_hour = limits["max_sessions_per_hour"]
    if sessions_hour >= max_hour and now - hour_start < 3600:
        reasons.append((
            int(3600 - (now - hour_start)) + 30,
            f"시간당 {max_hour}세션 한도",
        ))

    batch = limits["batch_size"]
    if state["sessions_since_rest"] >= batch and batch > 0:
        rest = limits["batch_rest_sec"]
        jitter = random.uniform(0.95, 1.1)
        reasons.append((int(rest * jitter), f"배치 휴식 ({batch}세션 후)"))

    if not reasons:
        return 0, ""

    wait, reason = max(reasons, key=lambda x: x[0])
    return max(wait, 0), reason


def apply_wait(cfg: dict | None = None, logger=None) -> None:
    wait, reason = wait_seconds_before_session(cfg)
    if wait <= 0:
        return
    msg = f"[RateLimit] {reason} → {wait}초 대기"
    if logger:
        logger(msg)
    else:
        print(msg)
    time.sleep(wait)
    if "배치 휴식" in reason:
        record_batch_rest(cfg)


def status_summary(cfg: dict | None = None) -> str:
    limits = load_rate_config(cfg)
    state = get_state()
    wait, reason = wait_seconds_before_session(cfg)
    return (
        f"간격 {limits['min_session_gap_sec']}s · "
        f"시간당 {limits['max_sessions_per_hour']}회 · "
        f"이번시간 {state['sessions_this_hour']}회 · "
        f"연속429 {state['consecutive_429']}회 · "
        f"다음대기 {wait}s {reason}"
    )
