#!/usr/bin/env python3
"""Heartbeat progress-review signal; never schedules work or grants authority."""
import argparse
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

THREAD = '01a0e5ff-d1a0-70f2-828f-9fc997519d04'


CODE_ROOTS = ('services', 'apps', 'bundles', 'scripts')
CODE_EXTENSIONS = ('.py', '.ts', '.tsx', '.js', '.mjs', '.sql', '.sh')


def exact_file(repo, relative, roots):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] not in roots:
        raise ValueError('file outside permitted roots')
    if any(part.startswith('.') and part != '.evidence' for part in path.parts):
        raise ValueError('hidden file is not review material')
    if any(word in path.name.lower() for word in ('credential', 'secret', 'password', 'token', 'auth.json')):
        raise ValueError('sensitive file is not review material')
    current = repo
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('symlink material rejected')
    if not current.is_file() or current.stat().st_size > 1024 * 1024:
        raise ValueError('missing or oversized material')
    return current


def checkpoint_snapshot(repo, thread, checkpoint, context):
    cp = json.loads(exact_file(repo, checkpoint, ('.evidence',)).read_text())
    required = ('task_id', 'owner', 'authority_revision', 'step')
    if cp.get('schema') != 'aos-engineering-checkpoint/v1' or any(not cp.get(k) for k in required):
        raise ValueError('invalid checkpoint')
    if cp.get('thread') != thread or cp.get('repo') != str(repo):
        raise ValueError('checkpoint identity mismatch')
    if not checkpoint.startswith('.evidence/' + cp['task_id'] + '/'):
        raise ValueError('checkpoint outside task evidence directory')
    authority = json.loads((context / 'memory/authority.json').read_text())
    receipt = json.loads((context / 'memory/receipts/tasks' / (cp['task_id'] + '.json')).read_text()) if Path(cp['task_id']).name == cp['task_id'] else {}
    leases = json.loads((context / 'memory/leases.json').read_text())['leases']
    matches = [l for l in leases if l['task_id'] == cp['task_id']]
    if (authority['project_revision'] != cp['authority_revision'] or receipt.get('owner') != cp['owner']
            or receipt.get('base_revision') != cp['authority_revision'] or len(matches) != 1
            or matches[0] != receipt or datetime.fromisoformat(receipt['lease_expires_at']).timestamp() <= time.time()):
        raise ValueError('checkpoint has no current owned lease')
    hashes = {}
    for key, roots in (('code_files', CODE_ROOTS), ('evidence_files', ('.evidence',))):
        files = cp.get(key, [])
        if not isinstance(files, list) or len(files) > 32:
            raise ValueError('invalid file list')
        for relative in files:
            if key == 'evidence_files' and not relative.startswith('.evidence/' + cp['task_id'] + '/'):
                raise ValueError('evidence outside task directory')
            file = exact_file(repo, relative, roots)
            if key == 'code_files':
                if file.suffix not in CODE_EXTENSIONS:
                    raise ValueError('not a code file')
                scoped = 'aos-platform/' + relative
                if any(scoped == scope or scoped.startswith(scope.rstrip('/') + '/') for scope in receipt.get('excluded_scope', [])):
                    raise ValueError('file inside excluded scope')
                if not any(scoped == scope or scoped.startswith(scope.rstrip('/') + '/') for scope in receipt['scope']):
                    raise ValueError('file outside task scope')
            hashes[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    if not hashes:
        raise ValueError('checkpoint must reference evidence or code')
    return dict((k, cp[k]) for k in required) | {'fingerprint': hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()}


def snapshot(repo, thread, checkpoint=None, context=None):
    repo = repo.resolve()
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=20).stdout.strip()
    paths = [f':(glob){root}/**/*.{ext}'
             for root in ('services', 'apps', 'bundles', 'scripts')
             for ext in ('py', 'ts', 'tsx', 'js', 'mjs', 'sql', 'sh')]
    latest = git('log', '-1', '--format=%H %ct', '--', *paths).split()
    result = dict(repo=str(repo), thread=thread, branch=git('branch', '--show-current'),
                  head=git('rev-parse', 'HEAD'), code_commit=latest[0] if latest else None,
                  code_time=int(latest[1]) if latest else 0)
    if checkpoint:
        result['checkpoint'] = checkpoint_snapshot(repo, thread, checkpoint, context)
    return result


def observe(previous, current, event, now):
    if current['branch'] != 'm1':
        raise ValueError('expected m1; no state update or work authorization')
    if previous:
        for field in ('thread', 'repo'):
            if previous[field] != current[field]:
                raise ValueError('progress state identity mismatch')
        if event <= previous['event']:
            return previous
    cp, old = current.get('checkpoint'), previous.get('checkpoint')
    same_task = bool(cp and old and all(cp[k] == old[k] for k in ('task_id', 'owner', 'authority_revision')))
    task_changed = same_task and cp['fingerprint'] != old['fingerprint']
    unchanged = (previous.get('unchanged_wakes', 0) + 1 if previous and
                 (not task_changed if cp else previous['code_commit'] == current['code_commit']) else 0)
    age = max(0, int(now - current['code_time']))
    review = unchanged >= 2 or age >= 1800 or not current['code_commit']
    action = ('TASK_PROGRESS_OBSERVED' if task_changed else 'REVIEW_REQUIRED') if cp else ('REVIEW_REQUIRED' if review else 'CONTINUE')
    return dict(current, schema='aos-wake-progress/v2', event=event,
                observed_at=now, unchanged_wakes=unchanged, code_age_seconds=age,
                action=action,
                meaning='Observation only: task file changes require content review; never work authorization, liveness or business completion.')


def recovery_guidance(*, user_paused, mechanism_authorized, active_tool, ownership_known,
                      outcome, risk, review_available, independent_candidate):
    """Conservative routing hints only; never performs recovery or changes Goal."""
    if user_paused and not mechanism_authorized:
        return 'RESPECT_USER_PAUSE'
    if not ownership_known:
        return 'RECONCILE_OWNERSHIP'
    if active_tool:
        return 'WAIT_EXISTING_TOOL'
    if outcome == 'unknown_external':
        return 'RECONCILE_RECEIPT_ONLY'
    if risk == 'formal' and not review_available:
        return 'CONTINUE_INDEPENDENT_CANDIDATE' if independent_candidate else 'FORMAL_ACTION_GATED'
    if outcome not in ('read_only', 'not_started', 'verified_local'):
        return 'RECONCILE_RECEIPT_ONLY'
    return 'REVIEW_NEXT_SAFE_STEP'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True, help='heartbeat current_time_iso')
    parser.add_argument('--checkpoint', help='exact repo-relative .evidence checkpoint')
    parser.add_argument('--shadow', action='store_true', help='read observations without changing stored state')
    args = parser.parse_args()
    event_time = datetime.fromisoformat(args.event.replace('Z', '+00:00'))
    if event_time.utcoffset() is None:
        raise ValueError('event must include timezone')
    event = str(int(event_time.timestamp() * 1000)).zfill(16)
    repo = Path(__file__).resolve().parents[2]
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    context = repo.parent / 'docs/palantier/AOS项目开发上下文'
    if args.shadow:
        print(json.dumps(observe({}, snapshot(repo, THREAD, args.checkpoint, context), event, time.time()), ensure_ascii=False))
        return
    state = home / 'automations' / 'aos-2' / 'progress.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    with open(state.with_suffix('.lock'), 'a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(state.read_text()) if state.exists() else {}
        result = observe(previous, snapshot(repo, THREAD, args.checkpoint, context), event, time.time())
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
