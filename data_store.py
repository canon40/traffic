# -*- coding: utf-8 -*-
"""
클라우드(GCS) 데이터 동기화 — Cloud Run 재시작 후에도 rank_history 등 유지.
환경변수: GCS_BUCKET (선택), GCS_PREFIX (기본 traffic-data)
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PREFIX = os.environ.get("GCS_PREFIX", "traffic-data")

SYNC_FILES = (
    "rank_history.csv",
    "traffic_sessions.jsonl",
    "traffic_sessions.csv",
    ".scheduler_state.json",
)


def _bucket_name() -> str | None:
    return os.environ.get("GCS_BUCKET") or os.environ.get("GCS_DATA_BUCKET")


def _blob_path(filename: str) -> str:
    return f"{PREFIX.rstrip('/')}/{filename}"


def _client():
    from google.cloud import storage
    return storage.Client()


def pull_from_cloud() -> list[str]:
    bucket = _bucket_name()
    if not bucket:
        return []
    pulled = []
    try:
        client = _client()
        b = client.bucket(bucket)
        for name in SYNC_FILES:
            blob = b.blob(_blob_path(name))
            if not blob.exists():
                continue
            dest = ROOT / name
            blob.download_to_filename(str(dest))
            pulled.append(name)
    except Exception as e:
        print(f"[data_store] pull 실패: {e}")
    return pulled


def push_to_cloud(filenames: tuple[str, ...] | None = None) -> list[str]:
    bucket = _bucket_name()
    if not bucket:
        return []
    pushed = []
    try:
        client = _client()
        b = client.bucket(bucket)
        for name in filenames or SYNC_FILES:
            path = ROOT / name
            if not path.exists():
                continue
            blob = b.blob(_blob_path(name.replace("\\", "/")))
            blob.upload_from_filename(str(path))
            pushed.append(name)
    except Exception as e:
        print(f"[data_store] push 실패: {e}")
    return pushed


def cloud_enabled() -> bool:
    return bool(_bucket_name())
