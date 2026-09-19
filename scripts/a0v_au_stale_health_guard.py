#!/usr/bin/env python3
"""Read the exact AU stale-health retirement boundary without mutation."""

from __future__ import annotations

import json

import a0v_au_stale_health_retirement as retirement


def main() -> int:
    try:
        state = retirement.snapshot("active")
        print(json.dumps({
            "outcome": "AU_STALE_HEALTH_RETIREMENT_REQUIRED",
            "automaticAction": False,
            "state": state,
        }, ensure_ascii=False, default=str, indent=2))
        return 0
    except Exception as error:
        print(json.dumps({
            "outcome": "SAFE_BLOCKED",
            "automaticAction": False,
            "errorType": type(error).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
