"""CLI: python -m aos_api.jobs.retention_run"""
from __future__ import annotations

import json
import sys

from aos_api.db import init_schema
from aos_api.retention_jobs import run_retention


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    dry = "--dry-run" in args
    try:
        init_schema()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"init_schema: {exc}"}))
        return 2
    out = run_retention(force_dry=True if dry else None)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
