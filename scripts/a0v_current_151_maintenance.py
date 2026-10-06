"""142-to151 maintenance preflight; no service/database mutation entry point yet."""
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
THREAD='01a107a2-e9e4-7670-bc44-1144fa9b27e2'
OWNER='codex-'+THREAD
TASK='current151-maintenance-20261006'
BASE='AOS-001369'
SCOPES=tuple('aos-platform/maintenance/current-preview-'+n for n in ('database','api','web'))

class Maintenance151Blocked(ValueError):
    pass


def require_task(task,leases,*,revision,thread,delivered,now):
    if thread!=THREAD or revision!=BASE or task.get('base_revision')!=BASE:
        raise Maintenance151Blocked('MAINTENANCE_151_BASELINE_DRIFT')
    if task.get('task_id')!=TASK or task.get('owner')!=OWNER or task.get('status')!='ACTIVE' or delivered:
        raise Maintenance151Blocked('MAINTENANCE_151_TASK_IDENTITY_REQUIRED')
    if not set(SCOPES)<=set(task.get('scope',[])):
        raise Maintenance151Blocked('MAINTENANCE_151_RESOURCE_SCOPE_REQUIRED')
    if [x for x in leases if x.get('task_id')==TASK]!=[task]:
        raise Maintenance151Blocked('MAINTENANCE_151_EXACT_LEASE_REQUIRED')
    try:
        expiry=datetime.fromisoformat(task['lease_expires_at'])
        valid=expiry.tzinfo is not None and now.tzinfo is not None and expiry.astimezone(timezone.utc)>now.astimezone(timezone.utc)
    except (KeyError,TypeError,ValueError):
        valid=False
    if not valid:
        raise Maintenance151Blocked('MAINTENANCE_151_FUTURE_LEASE_REQUIRED')


def read_task(*,thread):
    memory=ROOT.parent/'docs/palantier/AOS项目开发上下文/memory'
    authority=json.loads((memory/'authority.json').read_text())
    task=json.loads((memory/'receipts/tasks'/f'{TASK}.json').read_text())
    leases=json.loads((memory/'leases.json').read_text())['leases']
    require_task(task,leases,revision=authority['project_revision'],thread=thread,
                 delivered=(memory/'receipts/deliveries'/f'{TASK}.json').exists(),now=datetime.now(timezone.utc))
    return task
