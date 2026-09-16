"""Reload the current natural-chain API after the Q cursor ownership fix."""
from datetime import datetime, timezone
import json
import subprocess

import a0v_l_natural_api as natural_api


TASK = "A0V-NATURAL-CHAIN-MAIN-UPGRADE-20260915"
ROOT = natural_api.snapshot_api.ROOT


def load_launcher():
    """Preserve the existing independent snapshot worker and QYH Cron profile."""
    return natural_api.load_launcher()


def main():
    leases = json.loads(
        (ROOT.parent / "docs/palantier/AOS项目开发上下文/memory/leases.json").read_text()
    )["leases"]
    current = [row for row in leases if row["task_id"] == TASK]
    if (len(current) != 1 or current[0]["owner"] != "m1" or current[0]["status"] != "ACTIVE"
            or datetime.fromisoformat(current[0]["lease_expires_at"]) <= datetime.now(timezone.utc)
            or subprocess.check_output(["git", "branch", "--show-current"],
                                       cwd=ROOT, text=True).strip() != "m1"):
        raise ValueError("current m1 natural-chain upgrade lease required")
    with natural_api.snapshot_api.api_lock(
        natural_api.snapshot_api.STATE / "api.lock"
    ):
        load_launcher().main()


if __name__ == "__main__":
    main()
