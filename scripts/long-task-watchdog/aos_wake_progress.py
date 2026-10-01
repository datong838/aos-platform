#!/usr/bin/env python3
"""Heartbeat progress-review signal; never schedules work or grants authority."""
import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

THREAD = '01a0e5ff-d1a0-70f2-828f-9fc997519d04'


def snapshot(repo, thread):
    repo = repo.resolve()
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=20).stdout.strip()
    paths = [f':(glob){root}/**/*.{ext}'
             for root in ('services', 'apps', 'bundles', 'scripts')
             for ext in ('py', 'ts', 'tsx', 'js', 'mjs', 'sql', 'sh')]
    latest = git('log', '-1', '--format=%H %ct', '--', *paths).split()
    return dict(repo=str(repo), thread=thread, branch=git('branch', '--show-current'),
                head=git('rev-parse', 'HEAD'), code_commit=latest[0] if latest else None,
                code_time=int(latest[1]) if latest else 0)


def observe(previous, current, event, now):
    if current['branch'] != 'm1':
        raise ValueError('expected m1; no state update or work authorization')
    if previous:
        for field in ('thread', 'repo'):
            if previous[field] != current[field]:
                raise ValueError('progress state identity mismatch')
        if event <= previous['event']:
            return previous
    unchanged = (previous.get('unchanged_wakes', 0) + 1
                 if previous and previous['code_commit'] == current['code_commit'] else 0)
    age = max(0, int(now - current['code_time']))
    review = unchanged >= 2 or age >= 1800 or not current['code_commit']
    return dict(current, schema='aos-wake-progress/v1', event=event,
                observed_at=now, unchanged_wakes=unchanged, code_age_seconds=age,
                action='REVIEW_REQUIRED' if review else 'CONTINUE',
                meaning='No-new-code signal only; inspect real work, leases and evidence. Not a business verdict.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True, help='heartbeat current_time_iso')
    args = parser.parse_args()
    event_time = datetime.fromisoformat(args.event.replace('Z', '+00:00'))
    if event_time.utcoffset() is None:
        raise ValueError('event must include timezone')
    event = str(int(event_time.timestamp() * 1000)).zfill(16)
    repo = Path(__file__).resolve().parents[2]
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    state = home / 'automations' / 'aos-2' / 'progress.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    with open(state.with_suffix('.lock'), 'a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(state.read_text()) if state.exists() else {}
        result = observe(previous, snapshot(repo, THREAD), event, time.time())
        if result != previous:
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', dir=state.parent, delete=False) as f:
                    temp_name = f.name
                    json.dump(result, f, ensure_ascii=False, indent=2)
                    f.flush(); os.fsync(f.fileno())
                os.replace(temp_name, state)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
