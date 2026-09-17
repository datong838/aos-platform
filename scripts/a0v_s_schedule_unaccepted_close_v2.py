#!/usr/bin/env python3
"""Close S baseline Policy v2's proven pre-target discovery failure."""

import argparse
import json

import a0v_s_schedule_unaccepted_close as base


base.STATE = base.ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/schedule-closure-v2"
base.OCCURRENCE = "34733f17-f1ce-582d-b1b6-585a96aee2ff"
base.KEY = "a0v-s-baseline-v2-pre-target-close-20260917"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply", "audit"))
    args = parser.parse_args()
    print(json.dumps(getattr(base, args.phase)(), ensure_ascii=False, sort_keys=True, default=str))
