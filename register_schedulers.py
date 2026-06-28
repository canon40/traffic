# -*- coding: utf-8 -*-
"""Windows 작업 스케줄러 등록 (StartWhenAvailable + 로그인 보충)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK_DAILY = "NanumLab-DailyRankTrack"
TASK_CATCHUP = "NanumLab-StartupCatchup"
RUN_TIME = "09:00"


def schtasks(*args: str) -> int:
    cmd = ["schtasks", *args]
    print(">", " ".join(cmd))
    return subprocess.call(cmd)


def register_daily() -> int:
    xml_path = ROOT / "tasks" / "daily_rank_task.xml"
    xml_path.parent.mkdir(exist_ok=True)
    run_bat = str(ROOT / "run_daily_rank_track.bat")
    work_dir = str(ROOT)

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T{RUN_TIME}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>{run_bat}</Command>
      <Arguments>--silent</Arguments>
      <WorkingDirectory>{work_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""
    xml_path.write_text(xml, encoding="utf-16")
    schtasks("/delete", "/tn", TASK_DAILY, "/f")
    return schtasks("/create", "/tn", TASK_DAILY, "/xml", str(xml_path), "/f")


def register_catchup() -> int:
    catchup_bat = str(ROOT / "run_startup_catchup.bat")
    schtasks("/delete", "/tn", TASK_CATCHUP, "/f")
    return schtasks(
        "/create", "/tn", TASK_CATCHUP,
        "/tr", f"{catchup_bat} --silent",
        "/sc", "onlogon",
        "/delay", "0002:00",
        "/f",
    )


def main() -> int:
    print("=" * 50)
    print("스케줄러 등록")
    print("=" * 50)
    rc1 = register_daily()
    rc2 = register_catchup()
    if rc1 or rc2:
        print("\n일부 등록 실패 - 관리자 권한으로 다시 실행하세요.")
        return 1
    print("\n완료:")
    print(f"  - {TASK_DAILY}: 매일 {RUN_TIME}, PC 꺼져 있으면 켜진 뒤 실행")
    print(f"  - {TASK_CATCHUP}: 로그인 2분 후 보충")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
