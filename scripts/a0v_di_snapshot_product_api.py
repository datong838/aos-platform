#!/usr/bin/env python3
"""Run the shared independent snapshot worker under DI's exact lease and launcher."""
from __future__ import annotations
import a0v_di_successor_business as successor
successor.setup()
import a0v_snapshot_product_api as worker  # noqa: E402
worker.STATE = successor.STATE.parent / "snapshot-worker"
worker.TASK = "A0V-DI-SNAPSHOT-WORKER-20260922"
if __name__ == "__main__":
    worker.main()
