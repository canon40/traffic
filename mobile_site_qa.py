import json
import random
import time
from datetime import datetime

import uiautomator2 as u2


CONFIG_PATH = "site_qa_config.json"
LOG_PATH = "qa_log.txt"

DEFAULT_CONFIG = {
    "target_urls": [
        "https://permacoat.store/",
    ],
    "iterations": 3,
    "stay_seconds_min": 60,
    "stay_seconds_max": 120,
    "scroll_passes_min": 6,
    "scroll_passes_max": 10,
}


def log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if isinstance(cfg, dict):
                merged = dict(DEFAULT_CONFIG)
                merged.update(cfg)
                return merged
    except FileNotFoundError:
        pass
    return DEFAULT_CONFIG


def open_url(d: u2.Device, url: str) -> None:
    d.shell(f'am start -a android.intent.action.VIEW -d "{url}"')
    time.sleep(5)


def smooth_scroll(d: u2.Device, passes: int) -> None:
    for _ in range(passes):
        steps = random.randint(18, 28)
        d.swipe(500, 1500, 500, 500, steps=steps)
        time.sleep(random.uniform(0.8, 2.0))


def take_screenshot(d: u2.Device, prefix: str) -> str:
    fname = f"{prefix}_{int(time.time())}.png"
    d.screenshot(fname)
    return fname


def run_once(d: u2.Device, url: str, cfg: dict) -> None:
    log(f"OPEN {url}")
    open_url(d, url)

    top_shot = take_screenshot(d, "top")
    log(f"SCREENSHOT {top_shot}")

    passes = random.randint(cfg["scroll_passes_min"], cfg["scroll_passes_max"])
    log(f"SCROLL passes={passes}")
    smooth_scroll(d, passes)

    mid_shot = take_screenshot(d, "after_scroll")
    log(f"SCREENSHOT {mid_shot}")

    stay = random.randint(cfg["stay_seconds_min"], cfg["stay_seconds_max"])
    log(f"STAY {stay}s")
    time.sleep(stay)

    end_shot = take_screenshot(d, "end")
    log(f"SCREENSHOT {end_shot}")
    log("DONE")


def main() -> None:
    cfg = load_config()
    d = u2.connect()

    urls = cfg["target_urls"]
    iters = int(cfg["iterations"])

    log(f"START iters={iters} urls={len(urls)}")

    for i in range(iters):
        url = random.choice(urls)
        log(f"ITER {i+1}/{iters}")
        try:
            run_once(d, url, cfg)
        except Exception as e:
            log(f"ERROR {e}")
        time.sleep(random.uniform(3, 8))

    log("FINISH")


if __name__ == "__main__":
    main()

