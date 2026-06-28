# -*- coding: utf-8 -*-
"""세션별 User-Agent·뷰포트 로테이션 (PC + 모바일 믹스)."""
from __future__ import annotations

import random
from typing import Any

BROWSER_PROFILES: list[dict[str, Any]] = [
    {
        "label": "Chrome/Win",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1920, "height": 1080},
        "is_mobile": False,
    },
    {
        "label": "Edge/Win",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
        ),
        "viewport": {"width": 1536, "height": 864},
        "is_mobile": False,
    },
    {
        "label": "Chrome/Mac",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1440, "height": 900},
        "is_mobile": False,
    },
    {
        "label": "Safari/Mac",
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
        ),
        "viewport": {"width": 1440, "height": 900},
        "is_mobile": False,
    },
    {
        "label": "Chrome/Android",
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "viewport": {"width": 412, "height": 915},
        "is_mobile": True,
        "device_scale_factor": 2.625,
    },
    {
        "label": "Safari/iPhone",
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 "
            "Mobile/15E148 Safari/605.1.15"
        ),
        "viewport": {"width": 390, "height": 844},
        "is_mobile": True,
        "device_scale_factor": 3,
    },
    {
        "label": "Whale/Win",
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Whale/3.25.232.19 Safari/537.36"
        ),
        "viewport": {"width": 1366, "height": 768},
        "is_mobile": False,
    },
]


def pick_random_profile() -> dict[str, Any]:
    return {**random.choice(BROWSER_PROFILES)}


def profile_hint(profile: dict[str, Any], max_len: int = 40) -> str:
    label = profile.get("label", "?")
    ua = profile.get("user_agent", "")[:max_len]
    return f"{label} | {ua}..."


def context_options(profile: dict[str, Any]) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "user_agent": profile["user_agent"],
        "viewport": profile["viewport"],
        "locale": "ko-KR",
        "timezone_id": "Asia/Seoul",
        "is_mobile": profile.get("is_mobile", False),
    }
    if profile.get("device_scale_factor"):
        opts["device_scale_factor"] = profile["device_scale_factor"]
    if profile.get("is_mobile"):
        opts["has_touch"] = True
    return opts
