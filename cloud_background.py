# -*- coding: utf-8 -*-
"""
Cloudtype / Cloud Run 24시간 백그라운드 (PC 불필요).
- 순위 추적 스케줄러 자동 시작
- 일 1회 daily_rank_track
- GCS 동기화 (설정 시)
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
_leader_lock = threading.Lock()
_started = False
_threads: list[threading.Thread] = []


def _env_true(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _log(msg: str) -> None:
    line = f"[cloud_bg {datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    log_file = ROOT / "cloud_background.log"
    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _try_leader() -> bool:
    """멀티 워커 중 1개만 백그라운드 실행."""
    lock_path = Path(os.environ.get("DATA_DIR", str(ROOT))) / ".cloud_bg_leader.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import fcntl  # Linux (Cloudtype)
        f = open(lock_path, "w")
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (ImportError, OSError, BlockingIOError):
        pass
    try:
        import msvcrt  # Windows 로컬 테스트
        f = open(lock_path, "w")
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        f.write(str(os.getpid()))
        f.flush()
        return True
    except (ImportError, OSError):
        return _env_true("FORCE_BACKGROUND_LEADER", "1")


def _pull_cloud_data() -> None:
    try:
        from data_store import pull_from_cloud
        pulled = pull_from_cloud()
        if pulled:
            _log(f"GCS 복원: {', '.join(pulled)}")
    except Exception as e:
        _log(f"GCS pull 스킵: {e}")


def _push_cloud_data() -> None:
    try:
        from data_store import push_to_cloud
        pushed = push_to_cloud()
        if pushed:
            _log(f"GCS 저장: {', '.join(pushed)}")
    except Exception as e:
        _log(f"GCS push 실패: {e}")


def _run_daily_rank_once() -> None:
    _log("일일 순위 추적 시작")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "daily_rank_track.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        _log("일일 순위 추적 완료")
    else:
        _log(f"일일 순위 추적 실패: {(proc.stderr or '')[-300:]}")
    _push_cloud_data()


def _daily_rank_loop() -> None:
    """매일 지정 시각(기본 09:30 KST)에 1회 실행."""
    target_hour = int(os.environ.get("DAILY_RANK_HOUR", "9"))
    target_min = int(os.environ.get("DAILY_RANK_MINUTE", "30"))
    last_run_date = ""

    while True:
        try:
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if now.hour == target_hour and now.minute >= target_min and last_run_date != today:
                from scheduler_state import is_done_today
                if not is_done_today("daily_rank_track"):
                    _run_daily_rank_once()
                last_run_date = today
        except Exception as e:
            _log(f"daily loop 오류: {e}")
        time.sleep(60)


def _start_flask_scheduler() -> None:
    """app 모듈의 스케줄러 스레드 시작 (지연 import)."""
    try:
        import importlib
        flask_app = importlib.import_module("app")
        if flask_app.scheduler_running:
            _log("Flask 스케줄러 이미 실행 중")
            return
        flask_app.stop_event.clear()
        flask_app.scheduler_running = True
        t = threading.Thread(target=flask_app.scheduler_loop, daemon=True)
        t.start()
        flask_app.scheduler_thread = t
        _log("Flask 순위 스케줄러 시작")
    except Exception as e:
        _log(f"Flask 스케줄러 시작 실패: {e}")


def _rank_sweep_loop() -> None:
    """Playwright 없이 순위 API 스윕 (ENABLE_CLOUD_TRAFFIC와 독립)."""
    interval_h = int(os.environ.get("CLOUD_RANK_SWEEP_INTERVAL_HOURS", "4"))
    time.sleep(120)
    while True:
        try:
            _log("클라우드 순위 스윕 시작")
            from rank_tracker import build_completion_report, track_all_keywords
            results = track_all_keywords(logger=_log)
            report = build_completion_report(results)
            _log(report.get("summary", "순위 스윕 완료"))
            _push_cloud_data()
        except Exception as e:
            _log(f"순위 스윕 오류: {e}")
        time.sleep(max(3600, interval_h * 3600))


def _cloud_traffic_loop() -> None:
    """
    Playwright 트래픽 캠페인 (GCP VM 권장 — Cloudtype 512MB에서는 비활성).
    """
    interval_h = int(os.environ.get("CLOUD_TRAFFIC_INTERVAL_HOURS", "6"))
    time.sleep(300)
    while True:
        try:
            if _env_true("ENABLE_CLOUD_PLAYWRIGHT"):
                _log("Playwright focus 캠페인 1회")
                subprocess.run(
                    [sys.executable, str(ROOT / "focus_campaign.py"), "--headless", "--loop"],
                    cwd=str(ROOT),
                    timeout=86400,
                )
        except Exception as e:
            _log(f"cloud traffic 오류: {e}")
        time.sleep(max(3600, interval_h * 3600))


def start_cloud_services() -> None:
    global _started
    with _leader_lock:
        if _started:
            return
        if not _env_true("AUTO_START_BACKGROUND", "1"):
            _log("AUTO_START_BACKGROUND=0 — 백그라운드 미시작")
            return
        if not _try_leader():
            _log("다른 워커가 리더 — 백그라운드 스킵")
            return

        _started = True
        _log("=== Cloudtype 24h 백그라운드 시작 ===")
        _pull_cloud_data()

        if _env_true("AUTO_START_SCHEDULER", "1"):
            _start_flask_scheduler()

        t_daily = threading.Thread(target=_daily_rank_loop, daemon=True, name="daily-rank")
        t_daily.start()
        _threads.append(t_daily)

        if _env_true("ENABLE_CLOUD_RANK_SWEEP", "1"):
            t_sweep = threading.Thread(target=_rank_sweep_loop, daemon=True, name="rank-sweep")
            t_sweep.start()
            _threads.append(t_sweep)

        if _env_true("ENABLE_CLOUD_TRAFFIC", "0"):
            t_traffic = threading.Thread(target=_cloud_traffic_loop, daemon=True, name="cloud-traffic")
            t_traffic.start()
            _threads.append(t_traffic)

        _log(
            f"설정: 스케줄러={os.environ.get('AUTO_START_SCHEDULER', '1')} "
            f"순위스윕={os.environ.get('ENABLE_CLOUD_RANK_SWEEP', '1')} "
            f"트래픽={os.environ.get('ENABLE_CLOUD_TRAFFIC', '0')} "
            f"일일={os.environ.get('DAILY_RANK_HOUR', '9')}:{os.environ.get('DAILY_RANK_MINUTE', '30')} "
            f"DATA_DIR={os.environ.get('DATA_DIR', ROOT)}"
        )


def background_status() -> dict:
    try:
        import importlib
        flask_app = importlib.import_module("app")
        sched = getattr(flask_app, "scheduler_running", False)
    except Exception:
        sched = False
    return {
        "leader": _started,
        "scheduler_running": sched,
        "auto_start": _env_true("AUTO_START_BACKGROUND", "1"),
        "data_dir": os.environ.get("DATA_DIR", str(ROOT)),
        "cloud_storage": bool(os.environ.get("GCS_BUCKET")),
        "threads": [t.name for t in _threads if t.is_alive()],
    }
