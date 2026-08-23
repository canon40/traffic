# -*- coding: utf-8 -*-
"""playwright-stealth 1.x(stealth_sync) / 2.x(Stealth) 호환."""
from __future__ import annotations

import logging

log = logging.getLogger("stealth_compat")


def apply_stealth_sync(page) -> bool:
    try:
        from playwright_stealth import Stealth

        Stealth().apply_stealth_sync(page)
        return True
    except Exception:
        pass
    try:
        from playwright_stealth import stealth_sync

        stealth_sync(page)
        return True
    except Exception as exc:
        log.warning("stealth sync 적용 실패: %s", exc)
        return False


async def apply_stealth_async(page) -> bool:
    try:
        from playwright_stealth import Stealth

        await Stealth().apply_stealth_async(page)
        return True
    except Exception:
        pass
    try:
        from playwright_stealth import stealth_async

        await stealth_async(page)
        return True
    except Exception as exc:
        log.warning("stealth async 적용 실패: %s", exc)
        return False
