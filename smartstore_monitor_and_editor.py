"""
Outil conforme: suivi de rang (SERP) + logs cumulés.

- Mesure la position de votre site pour une liste de mots-clés via une API officielle.
- Écrit deux logs:
  - `report.csv` (structuré, cumulatif)
  - `work_log.txt` (lisible, cumulatif)

Ce module n’implémente pas d’automatisation "search→click", ni de génération de trafic,
ni de contournements (proxy/IP change, UA rotation, etc.).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

CONFIG_FILE = Path("traffic_config.json")
REPORT_CSV = Path("report.csv")
WORK_LOG = Path("work_log.txt")


@dataclass(frozen=True)
class RankResult:
    keyword: str
    rank: Optional[int]
    url: str


def now_iso_local() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def ensure_report_header() -> None:
    if REPORT_CSV.exists():
        return
    with REPORT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            ["started_at", "engine", "keyword", "target_host", "rank", "success", "found_url", "error"]
        )


def record_work_log(keyword: str, current_rank: Optional[int], status: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rank_part = f"{current_rank}위" if current_rank is not None else "미노출/미측정"
    msg = f"[{now}] 키워드: {keyword} | 현재순위: {rank_part} | 상태: {status}"
    with WORK_LOG.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def write_report_row(
    *,
    started_at: str,
    engine: str,
    keyword: str,
    target_host: str,
    rank: Optional[int],
    success: bool,
    found_url: str = "",
    error: str = "",
) -> None:
    ensure_report_header()
    with REPORT_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                started_at,
                engine,
                keyword,
                target_host,
                rank if rank is not None else "",
                success,
                found_url,
                error,
            ]
        )


def load_config() -> dict:
    """
    Utilise `traffic_config.json` si présent.
    Champs supportés (minimum):
      - keywords: list[str]
      - target_host: str (ex: "permacoat.store")  (ou `target_url` par compat)
      - max_pages: int (pages * 10 résultats)
      - min_sleep: float (secondes, optionnel)
      - max_sleep: float (secondes, optionnel)
      - report_file: str (optionnel, fichier "trend")
    """
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
            return cfg if isinstance(cfg, dict) else {}
    return {
        "keywords": [],
        "target_host": "permacoat.store",
        "max_pages": 5,
        "min_sleep": 0,
        "max_sleep": 0,
        "report_file": "rank_trend_report.csv",
    }


def append_trend_row(trend_path: Path, keyword: str, rank: Optional[int]) -> None:
    file_exists = trend_path.exists()
    with trend_path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not file_exists:
            w.writerow(["datetime", "keyword", "rank", "note"])
        note = ""
        if rank is not None and 11 <= int(rank) <= 30:
            note = "1페이지 근접!"
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), keyword, rank if rank is not None else "", note])


def google_cse_rank(keyword: str, target_host: str, pages: int) -> RankResult:
    """
    Google Custom Search JSON API (officiel).
    Env requis: GOOGLE_API_KEY, GOOGLE_CSE_ID
    """
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    cx = os.environ.get("GOOGLE_CSE_ID", "")
    if not api_key or not cx:
        raise RuntimeError("Variables d'environnement manquantes: GOOGLE_API_KEY / GOOGLE_CSE_ID")

    target_host = target_host.lower()
    best_rank: Optional[int] = None
    best_url = ""

    for page in range(max(1, pages)):
        start = page * 10 + 1
        params = {"key": api_key, "cx": cx, "q": keyword, "start": start, "num": 10}
        r = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        items = data.get("items", []) or []
        for i, item in enumerate(items, start=1):
            rank = page * 10 + i
            link = item.get("link", "")
            if link and target_host in host(link):
                if best_rank is None or rank < best_rank:
                    best_rank = rank
                    best_url = link

    return RankResult(keyword=keyword, rank=best_rank, url=best_url)


def naver_shop_rank(keyword: str, target_url: str, max_scrolls: int = 8) -> RankResult:
    """네이버 모바일 쇼핑 검색 순위 (Playwright)."""
    from naver_rank import check_naver_rank_sync

    product_id = ""
    try:
        parts = urlparse(target_url).path.strip("/").split("/")
        if len(parts) >= 3 and parts[-2] == "products":
            product_id = parts[-1]
    except Exception:
        pass

    rank = check_naver_rank_sync(keyword, target_url, max_scrolls=max_scrolls)
    found_url = target_url if rank > 0 else ""
    return RankResult(keyword=keyword, rank=rank if rank > 0 else None, url=found_url)


def run_monitoring() -> int:
    cfg = load_config()
    keywords = cfg.get("keywords") or []
    # compat: certains configs utilisent target_url au lieu de target_host
    target_host = (cfg.get("target_host") or cfg.get("target_url") or "permacoat.store").strip()
    pages = int(cfg.get("max_pages", 5))
    min_sleep = float(cfg.get("min_sleep", 0) or 0)
    max_sleep = float(cfg.get("max_sleep", 0) or 0)
    trend_path = Path(str(cfg.get("report_file") or "rank_trend_report.csv"))
    started_at = now_iso_local()
    target_urls = cfg.get("target_urls") or []
    default_target_url = target_urls[0] if target_urls else ""
    keyword_tasks = cfg.get("keyword_tasks") or []
    task_by_keyword: dict[str, str] = {}
    for t in keyword_tasks:
        kw = str(t.get("keyword", "")).strip()
        url = str(t.get("product_url") or "").strip()
        if kw and url:
            task_by_keyword[kw] = url

    if not keywords:
        print("Aucun mot-clé: ajoutez `keywords` dans traffic_config.json.", flush=True)
        return 2

    print(
        f"[monitor] started_at={started_at} keywords={len(keywords)} target_host={target_host} pages={pages}",
        flush=True,
    )

    for kw in keywords:
        target_url = task_by_keyword.get(kw, default_target_url)
        try:
            res = naver_shop_rank(kw, target_url=target_url, max_scrolls=int(cfg.get("max_pages", 8)))
            write_report_row(
                started_at=started_at,
                engine="naver_mobile",
                keyword=kw,
                target_host=target_url,
                rank=res.rank,
                success=True,
                found_url=res.url,
                error="",
            )
            record_work_log(kw, res.rank, "성공")
            append_trend_row(trend_path, kw, res.rank)
        except Exception as e:
            write_report_row(
                started_at=started_at,
                engine="naver_mobile",
                keyword=kw,
                target_host=target_url,
                rank=None,
                success=False,
                found_url="",
                error=str(e),
            )
            record_work_log(kw, None, f"실패: {e}")
            append_trend_row(trend_path, kw, None)

        # Throttling (optionnel)
        if max_sleep > 0 and max_sleep >= min_sleep:
            wait_s = random.uniform(min_sleep, max_sleep)
            print(f"[throttle] sleep {wait_s:.2f}s", flush=True)
            time.sleep(wait_s)

    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Rank tracker (conforme) + logs")
    p.add_argument("--monitor-only", action="store_true", help="Mesure de rang + logs")
    _ = p.parse_args()
    return run_monitoring()


if __name__ == "__main__":
    raise SystemExit(main())

