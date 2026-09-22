#!/usr/bin/env python3
"""Start DP's sole natural worker through the validated bounded supervisor."""
from __future__ import annotations
from pathlib import Path
import a0v_bw_terminal_supervisor as supervisor
import a0v_dp_successor_business as successor
ROOT = Path(__file__).resolve().parents[1]
successor.BW_ID = successor.DP_ID
successor.BW_GENERATION = successor.DP_GENERATION
supervisor.successor = successor
supervisor.WORKER = ROOT / "scripts/a0v_dp_snapshot_product_api.py"
supervisor._SETUP_COMPLETE = False
classify = supervisor.classify
read_rows = supervisor.read_rows
stop_worker = supervisor.stop_worker
supervise = supervisor.supervise
main = supervisor.main
if __name__ == "__main__":
    raise SystemExit(main())
