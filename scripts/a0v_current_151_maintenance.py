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
    source_intent=json.loads((backup/'intent.json').read_text())
    target_intent=json.loads((backup/'restore-phase/intent.json').read_text())
    target=json.loads(subprocess.check_output(['docker','--context',restore.DEST_CONTEXT,'inspect',target_intent['container']]))[0]
    restore.require_target(target,container=target_intent['container'],image=target_intent['image'])
    target_volumes=[x['Name'] for x in target['Mounts'] if x['Type']=='volume']
    source_volumes=[x['Name'] for x in item['Mounts'] if x['Type']=='volume']
    if len(target_volumes)!=1 or len(source_volumes)!=1:
        raise Maintenance151Blocked('UNIQUE_VOLUME_REQUIRED')
    require_resource_identity(dict(source_id=source_intent['source_id'],source_image=source_intent['image'],source_volume=source_intent['source_volume'],target_image=target_intent['image'],target_volume=target_intent['volume']),
        dict(source_id=item['Id'],source_image=item['Image'],source_volume=source_volumes[0],target_image=target['Image'],target_volume=target_volumes[0]))
    def target_query(q):
        return json.loads(subprocess.check_output(['docker','--context',restore.DEST_CONTEXT,'exec',target_intent['container'],'psql','-U','aos_app','-d',restore.SOURCE,'-v','ON_ERROR_STOP=1','-Atq','-c',"BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"+q+';COMMIT'],timeout=300))
    live_target=restore.full_snapshot(primitive,target_query,saved['role_names'])
    if live_target!=json.loads((backup/'restore-phase/snapshot.json').read_text()):
        raise Maintenance151Blocked('SECOND_RESTORE_LIVE_SNAPSHOT_DRIFT')
    restore.require_dump_restore_equivalence(saved,live_target)
    parameters=bootstrap._connection_parameters()
    if (parameters['host'],parameters['port'],parameters['dbname'])!=('127.0.0.1',18435,restore.SOURCE):
        raise Maintenance151Blocked('SOURCE_CONNECTION_DRIFT')
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
        conn.execute("SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public")
        current=restore.full_snapshot(primitive,lambda q:conn.execute(q).fetchone()['value'],saved['role_names'])
    if current!=saved:
        raise Maintenance151Blocked('SOURCE_CHANGED_SINCE_SECOND_BACKUP')
    restored151=audit_restored151(base=base,restore=restore,primitive=primitive)
    services=maintenance.current_services()
    if read_task(thread=thread)!=task or subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=head:
        raise Maintenance151Blocked('PREFLIGHT_BASELINE_CHANGED')
    return dict(outcome='CURRENT151_READ_ONLY_PREFLIGHT_GREEN',head=head,authority=BASE,source_version=current['version'],code_version='a0v_151',sql_hashes=sql_hashes,source_id=item['Id'],source_image=item['Image'],services=services,restored151=restored151,mutation_permission=False)


class ReadOnlyCatalogConnection:
    """Adapt fixed catalog SELECTs to original driver types, without granting login."""
    def __init__(self,query):
        self.query=query

    def execute(self,statement,parameters=()):
        import re
        from psycopg import sql
        if not re.match(r'^\s*SELECT\s',statement,re.IGNORECASE) or ';' in statement:
            raise Maintenance151Blocked('CATALOG_SELECT_REQUIRED')
        parts=statement.split('%s')
        if len(parts)!=len(parameters)+1:
            raise Maintenance151Blocked('CATALOG_PARAMETER_BINDING_REQUIRED')
        rendered=parts[0]
        for value,part in zip(parameters,parts[1:]):
            rendered+=sql.Literal(value).as_string()+part
        rows=self.query("SELECT coalesce(json_agg(row_to_json(audit_row)), '[]') AS value FROM ("+rendered+') audit_row')
        converted=[]
        for original in rows:
            row=dict(original)
            for key in ('oid','relowner','atttypid','proowner','prorettype','tgfoid'):
                if key in row:row[key]=int(row[key])
            if 'polroles' in row:row['polroles']=[int(x) for x in row['polroles']]
            if 'tgargs' in row:
                if not isinstance(row['tgargs'],str) or not row['tgargs'].startswith('\\x'):
                    raise Maintenance151Blocked('CATALOG_BYTEA_FORMAT_REQUIRED')
                row['tgargs']=bytes.fromhex(row['tgargs'][2:])
            converted.append(row)
        class Result:
            def fetchone(self):return converted[0] if converted else None
            def fetchall(self):return converted
        return Result()


def audit_restored151(*,base,restore,primitive):
    import subprocess
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    intent=json.loads((base/'same-image-phase/intent.json').read_text())
    container=intent['container']
    def inspect():
        return json.loads(subprocess.check_output(['docker','--context',restore.DEST_CONTEXT,'inspect',container]))[0]
    item=inspect()
    restore.require_target(item,container=container,image=intent['image'])
    def query(statement):
        return json.loads(subprocess.check_output(['docker','--context',restore.DEST_CONTEXT,'exec',container,
            'psql','-U','aos_app','-d',restore.SOURCE,'-v','ON_ERROR_STOP=1','-Atq','-c',
            "BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"+statement+';COMMIT'],timeout=300))
    expected=json.loads((base/'rehearsal-a151/after.json').read_text())
    if expected['version']!='a0v_151':raise Maintenance151Blocked('RESTORED_151_REQUIRED')
    restore.require_exact_restore(expected,restore.full_snapshot(primitive,query,expected['role_names']))
    require_withdrawal_fence(ReadOnlyCatalogConnection(query))
    restore.require_source_identity(item,inspect())
    return dict(container=container,version='a0v_151',full_snapshot='exact',withdrawal_fence='exact',source_mutations=0)


def require_resource_identity(expected,observed):
    keys={'source_id','source_image','source_volume','target_image','target_volume'}
    if set(expected)!=keys or set(observed)!=keys or any(not isinstance(expected[k],str) or not expected[k] or expected[k]!=observed[k] for k in keys):
        raise Maintenance151Blocked('BACKUP_RESOURCE_IDENTITY_DRIFT')


STEPS=('stop_clients','fence_tcp','snapshot_dump','independent_restore','migrate_steps','verify','restore_tcp','restart_clients','acceptance')

class Maintenance151Journal:
    """Persist intent before effects; unknown or failed attempts never auto-replay."""
    def __init__(self,directory,*,head):
        import re
        self.directory=Path(directory)
        if not self.directory.is_dir() or self.directory.is_symlink() or not re.fullmatch('[0-9a-f]{40}',head):
            raise Maintenance151Blocked('JOURNAL_IDENTITY_REQUIRED')
        self.binding=dict(head=head,thread=THREAD,task=TASK,authority=BASE)

    def _require_live_binding(self):
        import subprocess
        read_task(thread=self.binding['thread'])
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        if head!=self.binding['head'] or branch!='m1':
            raise Maintenance151Blocked('EXECUTION_HEAD_OR_BRANCH_DRIFT')

    def _write(self,name,data):
        import os
        try:fd=os.open(self.directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:raise Maintenance151Blocked('EXISTING_ATTEMPT_RECONCILE_ONLY') from None
        with os.fdopen(fd,'w') as f:
            json.dump(data,f,sort_keys=True);f.flush();os.fsync(f.fileno())
        fd=os.open(self.directory,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)

    def perform(self,step,operation):
        if step not in STEPS:raise Maintenance151Blocked('UNKNOWN_STEP')
        for prior in STEPS[:STEPS.index(step)]:
            for suffix in ('attempt','done'):
                p=self.directory/(prior+'-'+suffix+'.json')
                if not p.is_file() or p.is_symlink() or p.stat().st_size>65536:
                    raise Maintenance151Blocked('PRIOR_STEP_UNVERIFIED')
                try:r=json.loads(p.read_text())
                except (OSError,ValueError):raise Maintenance151Blocked('PRIOR_EVIDENCE_INVALID') from None
                if not isinstance(r,dict) or r.get('binding')!=self.binding or r.get('step')!=prior or (suffix=='done' and r.get('result',{}).get('status')!='verified'):
                    raise Maintenance151Blocked('PRIOR_BINDING_OR_VERIFICATION_DRIFT')
        self._require_live_binding()
        self._write(step+'-attempt.json',dict(binding=self.binding,step=step))
        self._require_live_binding()
        result=operation()
        if not isinstance(result,dict) or result.get('status')!='verified':
            raise Maintenance151Blocked('VERIFIED_POSTCONDITION_REQUIRED')
        self._write(step+'-done.json',dict(binding=self.binding,step=step,result=result))
        return result
