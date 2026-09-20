#!/usr/bin/env python3
"""Retire the clean never-active BM after its terminal preparation failure."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a0v_ecommerce_invalid_baseline_uninstall as retirement  # noqa: E402


BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
STATE = BASE / "retire-bm-failed-preparation"
retirement.INSTALLATION_ID = "370d4287-3402-40bb-b3da-d479633da7c4"
retirement.KEY = "a0v-bm-failed-preparation-uninstall-v1"
retirement.UNINSTALL_REASON = (
    "Retire clean never-active BM after terminal runtime artifact alias rejection"
)


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
        json.dump(value, stream, ensure_ascii=False, default=str, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = argparse.Namespace(
        apply=args.apply,
        database_name=retirement.DATABASE,
        trust_roots_file=BASE / "bm-trust-root-rotation/signing/trust-roots.json",
    )
    try:
        result, code = retirement.run(request), 0
        result["outcome"] = "BM_FAILED_PREPARATION_RETIREMENT_GREEN"
    except retirement.UninstallBlocked as exc:
        result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.code,
                        "message": str(exc)}, 2
    freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
