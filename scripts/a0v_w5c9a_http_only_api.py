#!/usr/bin/env python3
"""Run the bounded W5c9a HTTP-only profile with current private roots."""

import os
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import sys
import threading

import a0v_product_controlled_api as product


TASK = 'A0V-W5C9A-HTTP-ONLY-20260926'
BASE = Path(__file__).resolve().parents[2] / '.aos-recovery-20260920/state/q-advisor-baseline'
LEASES = Path(__file__).resolve().parents[2] / 'docs/palantier/AOS项目开发上下文/memory/leases.json'


def lease_deadline(path: Path, now: datetime) -> datetime | None:
    """Return only the unique exact live lease deadline; all uncertainty denies."""
    try:
        if now.tzinfo is None:
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
        leases = value['leases']
        if type(leases) is not list:
            return None
        matches = [item for item in leases if type(item) is dict
                   and item.get('task_id') == TASK]
        if len(matches) != 1:
            return None
        lease = matches[0]
        if (lease.get('owner') != 'm1' or lease.get('status') != 'ACTIVE'
                or lease.get('scope') != ['local-process/aos-api-18181']):
            return None
        deadline = datetime.fromisoformat(lease['lease_expires_at'])
        if deadline.tzinfo is None or deadline <= now:
            return None
        return deadline
    except (OSError, ValueError, TypeError, KeyError):
        return None


def watch_lease(path: Path, stop_event, terminate, *,
                clock=lambda: datetime.now(timezone.utc)) -> None:
    """Bound revocation detection to 30s and stop no later than lease expiry."""
    try:
        while not stop_event.is_set():
            now = clock()
            deadline = lease_deadline(path, now)
            if deadline is None:
                terminate()
                return
            delay = min(30.0, (deadline - now).total_seconds())
            if stop_event.wait(delay):
                return
    except Exception:
        terminate()


def load_launcher():
    launcher = product.load_launcher()
    launcher.DEFAULT_CREDENTIALS = BASE / 'bm-runtime-credentials/runtime-host-identities.json'
    launcher.TRUST_ROOTS = BASE / 'bm-trust-root-rotation/signing/trust-roots.json'
    launcher.BUNDLE_ROOT = BASE / 'bn-canonical-alias-registry/signed-bundles'
    return launcher


def main() -> None:
    os.environ['AOS_CONTROLLED_API_LEASE_TASK'] = TASK
    stop = threading.Event()
    guarded = len(sys.argv) > 1 and sys.argv[1] == 'serve'
    if guarded:
        if lease_deadline(LEASES, datetime.now(timezone.utc)) is None:
            raise SystemExit(2)
        watcher = threading.Thread(
            target=watch_lease,
            args=(LEASES, stop, lambda: os.kill(os.getpid(), signal.SIGTERM)),
            daemon=True, name='a0v-w5c9a-lease-guard')
        watcher.start()
    try:
        load_launcher().main()
    finally:
        stop.set()


if __name__ == '__main__':
    main()
