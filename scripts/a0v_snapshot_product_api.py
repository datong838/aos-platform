"""API-owned snapshot scheduler; preserves the independent, already running Host."""
import asyncio
from contextlib import contextmanager,asynccontextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
from a0v_event_complete_product_api import load_launcher as original_launcher

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260920/state/q-advisor-baseline/replacement-bf/snapshot-worker'
TASK='A0V-BF-SNAPSHOT-WORKER-20260920'
CODE_HASHES={str(p.relative_to(ROOT)):'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in (
    Path(__file__),ROOT/'services/aos-api/aos_api/main.py',
    ROOT/'services/aos-api/aos_api/routers/pipeline_snapshot_schedules.py',
    ROOT/'services/aos-api/aos_api/pipeline_snapshot_group_completion.py',
    ROOT/'services/aos-api/aos_api/extension_runtime/recoverable_store_attempt.py')}


@contextmanager
def api_lock(path):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with path.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def observe(app):
    state=app.state;worker=getattr(state,'snapshot_group_worker',None)
    task=getattr(state,'snapshot_group_worker_task',None)
    status=getattr(worker,'status','UNAVAILABLE')
    if status not in {'IDLE','RUNNING','STOPPING','STOPPED'}:status='UNAVAILABLE'
    error=getattr(worker,'last_error',None)
    if error not in {'SNAPSHOT_TICK_UNCONFIRMED'}:error=None
    return dict(pid=os.getpid(),observedAt=datetime.now(timezone.utc).isoformat(),workerState=status,
        workerTaskAlive=task is not None and not task.done(),workerError=error,
        hostInThisProcess=getattr(state,'extension_runtime_host_task',None) is not None,
        topology=getattr(state,'snapshot_group_worker_topology',None),executionAuthorized=False,
        loadedSourceHashes=CODE_HASHES)


def write_status(value):
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=STATE/('status.'+str(os.getpid())+'.tmp')
    with os.fdopen(os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600),'w') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
    temporary.replace(STATE/'status.json')


def load_launcher():
    launcher=original_launcher()
    launcher.API_FLAGS={**launcher.API_FLAGS,'AOS_SNAPSHOT_GROUP_WORKER_ENABLED':'true',
        'AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY':'independent','AOS_TWA_STORE':'pg'}
    original_preflight=launcher.preflight
    def preflight():
        result=original_preflight()
        from aos_api import main as api_main
        original_lifespan=api_main.app.router.lifespan_context
        @asynccontextmanager
        async def managed(app):
            stopped=asyncio.Event();reporter=None
            async def report():
                while not stopped.is_set():
                    write_status(observe(app))
                    try:await asyncio.wait_for(stopped.wait(),2)
                    except TimeoutError:pass
            try:
                async with original_lifespan(app):
                    status=observe(app)
                    from aos_api.tenant_scope import TenantScope
                    if (not status['workerTaskAlive'] or status['hostInThisProcess']
                        or status['topology']!='independent'
                        or app.state.snapshot_group_worker.scope!=TenantScope('org-org','dev-project')):
                        raise RuntimeError('independent snapshot worker startup not confirmed')
                    reporter=asyncio.create_task(report(),name='snapshot-worker-status-observer')
                    yield
            finally:
                stopped.set()
                if reporter is not None:await reporter
                write_status(observe(app))
        api_main.app.router.lifespan_context=managed
        return result
    launcher.preflight=preflight
    return launcher


def main():
    leases=json.loads((ROOT.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
    current=[x for x in leases if x['task_id']==TASK]
    if (len(current)!=1 or current[0]['owner']!='m1' or current[0]['status']!='ACTIVE'
        or datetime.fromisoformat(current[0]['lease_expires_at'])<=datetime.now(timezone.utc)):
        raise ValueError('current snapshot API lease required')
    launcher=load_launcher()
    if len(sys.argv)>1 and sys.argv[1]=='serve':
        with api_lock(STATE/'api.lock'):launcher.main()
    else:launcher.main()


if __name__=='__main__':main()
