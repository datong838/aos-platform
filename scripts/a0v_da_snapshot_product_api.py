#!/usr/bin/env python3
"""Run the shared independent snapshot worker under DA's exact lease and launcher."""
from __future__ import annotations
import a0v_da_successor_business as successor
successor.setup()
import a0v_snapshot_product_api as worker  # noqa: E402
worker.STATE = successor.STATE.parent / "snapshot-worker"
worker.TASK = "A0V-DA-SNAPSHOT-WORKER-20260921"
if __name__ == "__main__":
    worker.main()
