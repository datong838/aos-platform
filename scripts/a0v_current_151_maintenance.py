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


def _load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def preflight(*,thread):
    """Fresh source and original SQL evidence; does not grant mutation permission."""
    import hashlib
    import io
    import subprocess
    import psycopg
    from psycopg.rows import dict_row
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    task=read_task(thread=thread)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='m1':
        raise Maintenance151Blocked('M1_REQUIRED')
    subprocess.run(['git','diff','--exit-code','HEAD','--','services/aos-api/aos_api','services/aos-api/alembic'],cwd=ROOT,check=True,capture_output=True)
    base=ROOT.parent/'aos-recovery/current150-w5cb4-current150-restore-gate-20261005-154201'
    restore=_load('preflight_restore151',ROOT/'scripts/a0v_current_150_restore_gate.py')
    primitive=_load('preflight_snapshot151',ROOT/'scripts/a0v_current_142_restore_gate.py')
    maintenance=_load('preflight_process151',ROOT/'scripts/a0v_current_142_maintenance.py')
    bootstrap=_load('preflight_connect151',ROOT/'scripts/a0v_current_preview_bootstrap.py')
    config=Config(str(ROOT/'services/aos-api/alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
    if ScriptDirectory.from_config(config).get_heads()!=['a0v_151']:
        raise Maintenance151Blocked('CODE_HEAD_151_REQUIRED')
    prior=None
    sql_hashes={}
    for n in range(143,152):
        phase=base/f'rehearsal-a{n}'
        intent=json.loads((phase/'intent.json').read_text())
        if json.loads((phase/'terminal.json').read_text())['exit_code']!=0:
            raise Maintenance151Blocked('ORIGINAL_REHEARSAL_NOT_SUCCESSFUL')
        before=json.loads((phase/'before.json').read_text());after=json.loads((phase/'after.json').read_text())
        if before['version']!=f'a0v_{n-1}' or after['version']!=f'a0v_{n}' or (prior is not None and before!=prior):
            raise Maintenance151Blocked('REHEARSAL_NOT_CONTIGUOUS')
        prior=after
        output=io.StringIO();config.output_buffer=output
        command.upgrade(config,f'a0v_{n-1}:a0v_{n}',sql=True)
        digest=hashlib.sha256(output.getvalue().encode()).hexdigest()
        if digest!=intent['sql_sha256']:
            raise Maintenance151Blocked('CURRENT_SQL_DIFFERS_FROM_REHEARSED_SQL')
        sql_hashes[str(n)]=digest
    backup=base/'second-consistent-142-20261006'
    meta=json.loads((backup/'terminal.json').read_text())
    if primitive.sha(backup/'current-full.dump')!=meta['sha256'] or primitive.sha(backup/'globals-no-password.sql')!=meta['globals_sha256']:
        raise Maintenance151Blocked('SECOND_BACKUP_HASH_DRIFT')
    if json.loads((backup/'restore-phase/terminal.json').read_text())['exit_code']!=0:
        raise Maintenance151Blocked('SECOND_RESTORE_NOT_SUCCESSFUL')
    saved=json.loads((backup/'source.json').read_text())
    restore.require_dump_restore_equivalence(saved,json.loads((backup/'restore-phase/snapshot.json').read_text()))
    item=json.loads(subprocess.check_output(['docker','--context',restore.SOURCE_CONTEXT,'inspect',restore.SOURCE_CONTAINER]))[0]
    maintenance.require_source(item)
    parameters=bootstrap._connection_parameters()
    if (parameters['host'],parameters['port'],parameters['dbname'])!=('127.0.0.1',18435,restore.SOURCE):
        raise Maintenance151Blocked('SOURCE_CONNECTION_DRIFT')
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
        conn.execute("SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public")
        current=restore.full_snapshot(primitive,lambda q:conn.execute(q).fetchone()['value'],saved['role_names'])
    if current!=saved:
        raise Maintenance151Blocked('SOURCE_CHANGED_SINCE_SECOND_BACKUP')
    services=maintenance.current_services()
    if read_task(thread=thread)!=task or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=head:
        raise Maintenance151Blocked('PREFLIGHT_BASELINE_CHANGED')
    return dict(outcome='CURRENT151_READ_ONLY_PREFLIGHT_GREEN',head=head,authority=BASE,source_version=current['version'],code_version='a0v_151',sql_hashes=sql_hashes,source_id=item['Id'],source_image=item['Image'],services=services,mutation_permission=False)
