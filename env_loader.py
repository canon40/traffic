# -*- coding: utf-8 -*-
"""프로젝트·공용 .env 로드 (로컬 / Cloudtype)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_LOADED = False

_EXTRA_ENV_PATHS = (
    ROOT / ".env",
    Path(os.environ.get("TRAFFIC_ENV_FILE", "")) if os.environ.get("TRAFFIC_ENV_FILE") else None,
    Path(r"d:\@code\GEMMA4\Antigravity_Workspace\.env"),
)


def load_env(*, force: bool = False) -> bool:
    global _LOADED
    if _LOADED and not force:
        return True
    try:
        from dotenv import load_dotenv
    except ImportError:
        _LOADED = True
        return False

    for path in _EXTRA_ENV_PATHS:
        if path and path.is_file():
            load_dotenv(path, override=False)

    _LOADED = True
    return True


def api_keys_status() -> dict:
    load_env()
    return {
        "naver_open_api": bool(os.environ.get("NAVER_CLIENT_ID") and os.environ.get("NAVER_CLIENT_SECRET")),
        "serpapi": bool(os.environ.get("SERPAPI_KEY")),
        "google_cse": bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID")),
        "gcs": bool(os.environ.get("GCS_BUCKET") or os.environ.get("GCS_DATA_BUCKET")),
        "cron_secret": bool(os.environ.get("CRON_SECRET")),
    }
