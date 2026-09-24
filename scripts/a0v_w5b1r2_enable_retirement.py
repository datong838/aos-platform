#!/usr/bin/env python3
"""Use a new, isolated W5b1R2 intent for the original disable Owner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import a0v_w5b1r_enable_retirement as retirement

ROOT = Path(__file__).resolve().parents[1]
retirement.STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
                    "20260924-w5b1r2-enable-retirement")
retirement.KEY = "a0v-w5b1r2-retire-unconsumed-enable-20260924-v1"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request_disable", "process_disable", "audit"))
    print(json.dumps(getattr(retirement, parser.parse_args().phase)(),
                     ensure_ascii=False, default=str))
