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
    steps=STEPS
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
        if step not in self.steps:raise Maintenance151Blocked('UNKNOWN_STEP')
        for prior in self.steps[:self.steps.index(step)]:
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


def require_isolated151(item,*,name,image):
    import re
    mounts=item.get('Mounts',[])
    valid=(len(mounts)==1 and all(mounts[0].get(k)==v for k,v in
        dict(Type='volume',Name=name+'-data',Destination='/var/lib/postgresql/data',RW=True).items()))
    if (not re.fullmatch(r'current151-(source|restore)-[a-z0-9]+',name)
        or item['Name']!='/'+name or item['Image']!=image or not item['State']['Running']
        or item['HostConfig']['NetworkMode']!='none' or item['HostConfig']['Privileged']
        or any(item['NetworkSettings']['Ports'].values()) or not valid):
        raise Maintenance151Blocked('ISOLATED151_RESOURCE_REQUIRED')


METADATA151_ADDITIONS={'meta_object_type':('ProviderCapacityRequest','ProviderCapacitySourceReview'),
    'meta_action_type':('aip_request_provider_capacity','aip_review_provider_capacity_source')}

def normalize_metadata151(before,expected,actual,template_rows,live_rows):
    """Permit only four migration-created timestamps; preserve every old row."""
    import copy
    normalized=copy.deepcopy(actual)
    for table,names in METADATA151_ADDITIONS.items():
        old=before['metadata'][table];new=actual['metadata'][table]
        if (set(new)!=set(old)|set(names) or any(new.get(k)!=v for k,v in old.items())
            or actual['tables'][table]['count']!=len(old)+len(names)):
            raise Maintenance151Blocked('METADATA151_OLD_ROWS_OR_ADDITIONS_DRIFT')
        a={x['id']:x for x in template_rows[table]};b={x['id']:x for x in live_rows[table]}
        if len(template_rows[table])!=len(names) or len(live_rows[table])!=len(names) or set(a)!=set(names) or set(b)!=set(names):
            raise Maintenance151Blocked('METADATA151_EXACT_ROWS_REQUIRED')
        for name in names:
            for row in (a[name],b[name]):
                try:stamp=datetime.fromisoformat(row['created_at'])
                except (KeyError,TypeError,ValueError):raise Maintenance151Blocked('METADATA151_TIMESTAMP_REQUIRED') from None
                if stamp.tzinfo is None:raise Maintenance151Blocked('METADATA151_TIMESTAMP_REQUIRED')
            if {k:v for k,v in a[name].items() if k!='created_at'}!={k:v for k,v in b[name].items() if k!='created_at'}:
                raise Maintenance151Blocked('METADATA151_CONTENT_DRIFT')
            normalized['metadata'][table][name]=expected['metadata'][table][name]
        normalized['tables'][table]['sha256']=expected['tables'][table]['sha256']
    return normalized



def run_isolated151(*,thread):
    """Whole current-version window sequence on new isolated volumes only."""
    return _run_sequence151(thread=thread,current=False)


def run_current151(*,thread):
    read_task(thread=thread)
    return _run_sequence151(thread=thread,current=True)


def require_current151_action(args):
    if not args or args[0] not in ('exec','restart','inspect') or 'aos-a0v-recovery-pg' not in args:
        raise Maintenance151Blocked('CURRENT151_ACTION_FORBIDDEN')


def stop_services151(services,*,journal,maintenance):
    import os,signal,subprocess,time
    for service in services:
        journal._require_live_binding()
        original=service['fingerprint']
        observed=maintenance.read_service_candidate(pid=original['pid'],expected_argv=service['argv'],expected_cwd=service['cwd'],expected_port=service['port'],expected_child_argv=service['helper_argv'])
        maintenance.require_process(original,observed,executor_pid=os.getpid())
        journal._write(f"service-{service['port']}-stop-intent.json",dict(fingerprint=original))
        journal._require_live_binding()
        os.kill(original['pid'],signal.SIGTERM)
        for _ in range(100):
            probe=subprocess.run(['ps','-p',str(original['pid']),'-o','stat='],capture_output=True,text=True)
            listener=subprocess.run(['lsof','-nP',f"-iTCP:{service['port']}",'-sTCP:LISTEN','-t'],capture_output=True)
            if (probe.returncode!=0 or probe.stdout.strip().startswith('Z')) and not listener.stdout.strip():break
            time.sleep(.1)
        else:raise Maintenance151Blocked('SERVICE_STOP_UNKNOWN_RECONCILE_ONLY')
        for child in original['children']:
            probe=subprocess.run(['ps','-p',str(child['pid']),'-o','stat='],capture_output=True,text=True)
            if probe.returncode==0 and not probe.stdout.strip().startswith('Z'):raise Maintenance151Blocked('WEB_HELPER_DID_NOT_EXIT')
    return dict(status='verified',services_stopped=[x['port'] for x in services],forced_signals=0)


def restart_services151(services,*,journal,maintenance):
    import os,subprocess,time,urllib.request
    restarted=[]
    for service in services:
        journal._require_live_binding();port=service['port']
        listener=subprocess.run(['lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-t'],capture_output=True)
        if listener.stdout.strip():raise Maintenance151Blocked('RESTART_PORT_OCCUPIED_NO_DUPLICATE')
        if port==8080:
            preflight=subprocess.run(service['argv'][:-1],cwd=service['cwd'],capture_output=True,timeout=90)
            if preflight.returncode:raise Maintenance151Blocked('SIGNED_STARTUP_PREFLIGHT_FAILED')
            report=json.loads(preflight.stdout.strip().splitlines()[-1])
            if report['outcome']!='CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN' or report['version']!='a0v_151':raise Maintenance151Blocked('SIGNED_STARTUP_SCHEMA_DRIFT')
            journal._write('signed-startup-preflight.json',report)
        environment={k:os.environ[k] for k in ('PATH','HOME','TMPDIR','LANG') if k in os.environ}
        environment.update(service['environment'])
        journal._write(f'service-{port}-start-intent.json',dict(argv=service['argv'],cwd=service['cwd']))
        journal._require_live_binding()
        with os.fdopen(os.open(journal.directory/f'service-{port}.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as handle:
            process=subprocess.Popen(service['argv'],cwd=service['cwd'],env=environment,stdout=handle,stderr=handle,start_new_session=True)
        journal._write(f'service-{port}-started.json',dict(pid=process.pid))
        for _ in range(100):
            if process.poll() is not None:raise Maintenance151Blocked('RESTARTED_SERVICE_TERMINAL')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/'+('v1/ready' if port==8080 else ''),timeout=2) as response:
                    if response.status==200:break
            except OSError:pass
            time.sleep(.2)
        else:raise Maintenance151Blocked('RESTARTED_SERVICE_UNVERIFIED')
        observed=maintenance.read_service_candidate(pid=process.pid,expected_argv=service['argv'],expected_cwd=service['cwd'],expected_port=port,expected_child_argv=service['helper_argv'])
        restarted.append(dict(port=port,pid=process.pid,fingerprint=observed))
    return dict(status='verified',restarted=restarted,http_readonly_smoke=True,business_first_chain=False)


def _run_sequence151(*,thread,current):
    import hashlib,io,os,secrets,subprocess,time
    from alembic import command
    from alembic.config import Config
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    report=preflight(thread=thread)
    subprocess.run(['git','diff','--exit-code','HEAD','--','scripts/a0v_current_151_maintenance.py'],cwd=ROOT,check=True,capture_output=True)
    historic=ROOT.parent/'aos-recovery/current150-w5cb4-current150-restore-gate-20261005-154201'
    backup=historic/'second-consistent-142-20261006'
    restore=_load('isolated151_restore',ROOT/'scripts/a0v_current_150_restore_gate.py')
    primitive=_load('isolated151_snapshot',ROOT/'scripts/a0v_current_142_restore_gate.py')
    maintenance=_load('isolated151_window',ROOT/'scripts/a0v_current_142_maintenance.py')
    expected=json.loads((backup/'source.json').read_text())
    final_expected=json.loads((historic/'rehearsal-a151/after.json').read_text())
    image=json.loads((backup/'restore-phase/intent.json').read_text())['image']
    suffix=secrets.token_hex(6)
    state=ROOT.parent/('aos-recovery/current151-window-'+suffix)
    state.mkdir(mode=0o700)
    journal=Maintenance151Journal(state,head=report['head'])
    source,target='current151-source-'+suffix,'current151-restore-'+suffix
    if current:source=restore.SOURCE_CONTAINER
    docker=['docker','--context',restore.DEST_CONTEXT]
    tick=time.monotonic()
    def save(name,value):journal._write(name,value)
    save('intent.json',dict(binding=journal.binding,source=source,target=target,image=image,source_touched=current))
    def execute(args,data=None,check=True):
        journal._require_live_binding()
        selected=docker
        if current and restore.SOURCE_CONTAINER in args:
            require_current151_action(args)
            selected=['docker','--context',restore.SOURCE_CONTEXT]
            item=json.loads(subprocess.check_output(selected+['inspect',source]))[0]
            maintenance.require_source(item)
            if item['Id']!=report['source_id'] or item['Image']!=report['source_image']:
                raise Maintenance151Blocked('CURRENT151_SOURCE_IDENTITY_DRIFT')
        result=subprocess.run(selected+args,input=data,capture_output=True,timeout=180)
        if check and result.returncode:
            raise Maintenance151Blocked('ISOLATED151_COMMAND_FAILED_EXIT_'+str(result.returncode))
        return result
    def pg(name,statement,database=restore.SOURCE,tcp=False,check=True):
        if current and name==source and tcp:
            import psycopg
            from types import SimpleNamespace
            if database!=restore.SOURCE or statement not in ('SELECT 1','SELECT version_num FROM alembic_version'):
                raise Maintenance151Blocked('CURRENT151_TCP_READONLY_REQUIRED')
            journal._require_live_binding()
            bootstrap=_load('current151_bootstrap',ROOT/'scripts/a0v_current_preview_bootstrap.py')
            try:
                with psycopg.connect(**bootstrap._connection_parameters(),connect_timeout=3) as conn:
                    conn.read_only=True;value=conn.execute(statement).fetchone()[0]
                return SimpleNamespace(returncode=0,stdout=(str(value)+'\n').encode())
            except psycopg.OperationalError:
                if check:raise Maintenance151Blocked('CURRENT151_TCP_READ_FAILED') from None
                return SimpleNamespace(returncode=2,stdout=b'')
        return execute(['exec',name,'psql','-U','aos_app','-d',database,'-Atq','-v','ON_ERROR_STOP=1']+
            (['-h','127.0.0.1'] if tcp else [])+['-c',statement],check=check)
    def ready(name):
        for _ in range(30):
            if execute(['exec',name,'pg_isready','-U','aos_app'],check=False).returncode==0:return
            time.sleep(1)
        raise Maintenance151Blocked('ISOLATED151_NOT_READY')
    def inspect(name):
        item=json.loads(execute(['inspect',name]).stdout)[0]
        if current and name==source:maintenance.require_source(item)
        else:require_isolated151(item,name=name,image=image)
        return item
    def query(name,statement):
        return json.loads(pg(name,"BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"+statement+';COMMIT').stdout)
    def snapshot(name,roles):return restore.full_snapshot(primitive,lambda q:query(name,q),roles)
    def metadata_rows(name):
        from psycopg import sql
        return {table:query(name,'SELECT json_agg(row_to_json(t) ORDER BY id) AS value FROM (SELECT * FROM public.'+table+
            ' WHERE id IN ('+','.join(sql.Literal(x).as_string() for x in names)+')) t')
            for table,names in METADATA151_ADDITIONS.items()}
    template_rows=metadata_rows(json.loads((historic/'same-image-phase/intent.json').read_text())['container'])
    def require_final_snapshot():
        observed=snapshot(source,final_expected['role_names'])
        normalized=normalize_metadata151(expected,final_expected,observed,template_rows,metadata_rows(source))
        restore.require_dump_restore_equivalence(final_expected,normalized)
    globals_data=primitive.prepare_globals((backup/'globals-no-password.sql').read_bytes(),bootstrap='aos_app')
    for name in (source,target):
        if current and name==source:
            inspect(name);continue
        execute(['run','-d','--pull','never','--name',name,'--network','none','--cpus','1','--memory','768m',
            '--label','aos.restore-gate=20261006-151','--mount','type=volume,source='+name+'-data,target=/var/lib/postgresql/data',
            '-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image])
        ready(name);inspect(name)
        if name==source:
            execute(['exec','-i',name,'psql','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],globals_data)
    if not current:
        execute(['exec','-i',source,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],(backup/'current-full.dump').read_bytes())
    restore.require_dump_restore_equivalence(expected,snapshot(source,expected['role_names']))
    if pg(source,'SELECT 1',tcp=True).stdout.strip()!=b'1':raise Maintenance151Blocked('ISOLATED151_TCP_BASELINE_REQUIRED')
    listen_query="SELECT json_agg(x) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x"
    rows=json.loads(pg(source,listen_query).stdout)
    listen=pg(source,'SHOW listen_addresses').stdout.decode().strip()
    restore_statement=maintenance.listen_restore_statement(rows,effective=listen)
    save('listen-original.json',dict(rows=rows,effective=listen,restore_statement=restore_statement))
    services=report['services'] if current else None
    if current:save('services-original.json',services)
    journal.perform('stop_clients',lambda: stop_services151(services,journal=journal,maintenance=maintenance)
        if current else dict(status='verified',scope='isolated_no_application_clients'))
    def window():
        values=dict(listen_addresses=pg(source,'SHOW listen_addresses').stdout.decode().strip(),
            tcp_exit=pg(source,'SELECT 1',tcp=True,check=False).returncode,
            other_clients=int(pg(source,"SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()").stdout),
            prepared=int(pg(source,'SELECT count(*) FROM pg_prepared_xacts').stdout))
        maintenance.require_window(**values)
        return values
    def fence():
        pg(source,"ALTER SYSTEM SET listen_addresses=''")
        execute(['restart',source]);ready(source)
        return dict(status='verified',**window())
    journal.perform('fence_tcp',fence)
    def write_bytes(name,data):
        with os.fdopen(os.open(state/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
    def dump():
        window();restore.require_dump_restore_equivalence(expected,snapshot(source,expected['role_names']))
        data=execute(['exec',source,'pg_dump','-U','aos_app','-d',restore.SOURCE,'-Fc']).stdout
        write_bytes('window.dump',data)
        write_bytes('window-globals.sql',execute(['exec',source,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']).stdout)
        execute(['exec','-i',target,'pg_restore','-l'],data)
        return dict(status='verified',sha256=primitive.sha(state/'window.dump'),globals_sha256=primitive.sha(state/'window-globals.sql'),bytes=len(data))
    journal.perform('snapshot_dump',dump)
    def independent_restore():
        fresh_globals=primitive.prepare_globals((state/'window-globals.sql').read_bytes(),bootstrap='aos_app')
        execute(['exec','-i',target,'psql','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],fresh_globals)
        execute(['exec','-i',target,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],(state/'window.dump').read_bytes())
        restore.require_dump_restore_equivalence(expected,snapshot(target,expected['role_names']))
        window()
        return dict(status='verified',tables=len(expected['tables']))
    journal.perform('independent_restore',independent_restore)
    def migrate():
        config=Config(str(ROOT/'services/aos-api/alembic.ini'))
        config.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
        for n in range(143,152):
            window();inspect(source)
            if pg(source,'SELECT version_num FROM alembic_version').stdout.strip()!=f'a0v_{n-1}'.encode():raise Maintenance151Blocked('MIGRATION_VERSION_DRIFT')
            config.output_buffer=io.StringIO();command.upgrade(config,f'a0v_{n-1}:a0v_{n}',sql=True)
            data=config.output_buffer.getvalue().encode()
            if hashlib.sha256(data).hexdigest()!=report['sql_hashes'][str(n)]:raise Maintenance151Blocked('MIGRATION_SQL_HASH_DRIFT')
            save(f'migration-{n}-attempt.json',dict(binding=journal.binding,sha256=report['sql_hashes'][str(n)]))
            result=execute(['exec','-i',source,'psql','-U','aos_app','-d',restore.SOURCE,'-q','-v','ON_ERROR_STOP=1','-f','-'],data,check=False)
            save(f'migration-{n}-terminal.json',dict(exit_code=result.returncode))
            if result.returncode or pg(source,'SELECT version_num FROM alembic_version').stdout.strip()!=f'a0v_{n}'.encode():raise Maintenance151Blocked('MIGRATION_STEP_FAILED_RECONCILE_ONLY')
        return dict(status='verified',version='a0v_151',steps=9)
    journal.perform('migrate_steps',migrate)
    def verify():
        window()
        require_final_snapshot()
        require_withdrawal_fence(ReadOnlyCatalogConnection(lambda q:query(source,q)))
        return dict(status='verified',full_snapshot='exact_except_reviewed_check_associativity',withdrawal_fence='exact')
    journal.perform('verify',verify)
    def restore_tcp():
        pg(source,restore_statement);execute(['restart',source]);ready(source)
        if pg(source,'SELECT 1',tcp=True).stdout.strip()!=b'1' or json.loads(pg(source,listen_query).stdout)!=rows:raise Maintenance151Blocked('LISTEN_RESTORE_DRIFT')
        return dict(status='verified',original_config_restored=True)
    journal.perform('restore_tcp',restore_tcp)
    journal.perform('restart_clients',lambda: restart_services151(services,journal=journal,maintenance=maintenance)
        if current else dict(status='verified',scope='isolated_no_application_clients'))
    def acceptance():
        inspect(source);inspect(target)
        require_final_snapshot()
        if pg(source,'SELECT version_num FROM alembic_version',tcp=True).stdout.strip()!=b'a0v_151':raise Maintenance151Blocked('FINAL_VERSION_DRIFT')
        return dict(status='verified',schema='a0v_151',source_touched=current,business_first_chain=False)
    journal.perform('acceptance',acceptance)
    result=dict(outcome='CURRENT142_TO151_MAINTENANCE_API_WEB_GREEN_BROWSER_PENDING' if current else 'ISOLATED142_TO151_WINDOW_SEQUENCE_GREEN',state=str(state),source=source,target=target,head=report['head'],elapsed_seconds=round(time.monotonic()-tick,3),current_source_touched=current)
    save('result.json',result)
    return result


TENANT_TIMESTAMP_TABLES151=('meta_org','meta_workspace','meta_membership')


def build_tenant_timestamp_repair151(original,observed):
    """Build a narrowly scoped atomic CAS repair; this never executes SQL.

    Values must come from the verified original window restore and a freshly
    reconciled current snapshot. The separate zero-execution/backup/journal
    gates remain mandatory before applying this statement to any resource.
    """
    from psycopg import sql
    if not isinstance(original,dict) or not isinstance(observed,dict) or set(original)!=set(TENANT_TIMESTAMP_TABLES151) or set(observed)!=set(original):
        raise Maintenance151Blocked('TIMESTAMP_REPAIR_EXACT_TABLES_REQUIRED')
    updates=[]
    for table in TENANT_TIMESTAMP_TABLES151:
        before,after=original[table],observed[table]
        if not isinstance(before,list) or not isinstance(after,list) or len(before)!=1 or len(after)!=1:
            raise Maintenance151Blocked('TIMESTAMP_REPAIR_EXACT_EXISTING_ROWS_REQUIRED')
        a,b=before[0],after[0]
        if not isinstance(a,dict) or not isinstance(b,dict) or set(a)!=set(b) or {k for k in a if a[k]!=b[k]}!={'updated_at'}:
            raise Maintenance151Blocked('TIMESTAMP_REPAIR_ONLY_TIMESTAMP_DRIFT_ALLOWED')
        if (a.get('id') if table=='meta_org' else a.get('org_id'))!='org-org' or (table!='meta_org' and a.get('project_id')!='dev-project'):
            raise Maintenance151Blocked('TIMESTAMP_REPAIR_TENANT_SCOPE_REQUIRED')
        try:
            old_time=datetime.fromisoformat(a['updated_at']);new_time=datetime.fromisoformat(b['updated_at'])
            valid=old_time.tzinfo is not None and new_time.tzinfo is not None and new_time>old_time
        except (KeyError,ValueError,TypeError):valid=False
        if not valid:raise Maintenance151Blocked('TIMESTAMP_REPAIR_AWARE_FORWARD_DRIFT_REQUIRED')
        updates.append(sql.SQL('UPDATE public.{} AS t SET updated_at={}::timestamptz WHERE row_to_json(t)::jsonb = {}::jsonb; GET DIAGNOSTICS affected = ROW_COUNT; IF affected <> 1 THEN RAISE EXCEPTION \'TENANT_TIMESTAMP_CAS_MISMATCH\'; END IF;').format(
            sql.Identifier(table),sql.Literal(a['updated_at']),sql.Literal(json.dumps(b,sort_keys=True))).as_string())
    body='DECLARE affected integer; BEGIN '+' '.join(updates)+' END;'
    locks=sql.SQL(', ').join(sql.SQL('public.{}').format(sql.Identifier(t)) for t in sorted(TENANT_TIMESTAMP_TABLES151))
    return sql.SQL("BEGIN; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE; DO {}; COMMIT;").format(locks,sql.Literal(body))


class Repair151Journal(Maintenance151Journal):
    steps=('reconcile','stop_clients','fence_tcp','snapshot_dump','independent_restore','rehearse_repair','repair_timestamps','verify','restore_tcp','restart_clients','acceptance')


def require_failed_window151(records):
    import re
    binding=dict(head='ebac8fd094a8202b0e08f436cd9c09e8a0207d75',thread=THREAD,task=TASK,authority=BASE)
    try:
        intent=records['intent.json']
        valid=(intent['binding']==binding and intent['source']=='aos-a0v-recovery-pg' and intent['source_touched'] is True and intent['target']=='current151-restore-da8531053c83' and 'acceptance-done.json' not in records)
        for step in STEPS:
            attempt=records[step+'-attempt.json']
            valid=valid and attempt['binding']==binding and attempt['step']==step
            if step!='acceptance':
                done=records[step+'-done.json']
                valid=valid and done['binding']==binding and done['step']==step and done['result']['status']=='verified'
        for n in range(143,152):
            attempt=records[f'migration-{n}-attempt.json']
            valid=valid and attempt['binding']==binding and bool(re.fullmatch('[0-9a-f]{64}',attempt['sha256'])) and records[f'migration-{n}-terminal.json']['exit_code']==0
    except (KeyError,TypeError):valid=False
    if not valid:raise Maintenance151Blocked('EXACT_FAILED151_WINDOW_HISTORY_REQUIRED')
    return binding


def run_current151_repair(*,thread):
    """One claimed, backed-up repair phase for the known terminal startup drift."""
    import copy,hashlib,os,secrets,subprocess,time
    task=read_task(thread=thread)
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    subprocess.run(['git','diff','--exit-code','HEAD','--','scripts/a0v_current_151_maintenance.py','services/aos-api/aos_api','services/aos-api/alembic'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','merge-base','--is-ancestor','d7b5ad809df1778c29b2f849019204c68c6f8433',head],cwd=ROOT,check=True,capture_output=True)
    original=ROOT.parent/'aos-recovery/current151-window-da8531053c83'
    historic=ROOT.parent/'aos-recovery/current150-w5cb4-current150-restore-gate-20261005-154201'
    if not original.is_dir() or original.is_symlink():raise Maintenance151Blocked('ORIGINAL_WINDOW_REQUIRED')
    if any(p.is_symlink() for p in original.glob('*.json')):raise Maintenance151Blocked('ORIGINAL_WINDOW_SYMLINK_REFUSED')
    records={p.name:json.loads(p.read_text()) for p in original.glob('*.json') if p.name.endswith(('-attempt.json','-done.json','-terminal.json')) or p.name=='intent.json'}
    require_failed_window151(records)
    source_identity=json.loads((historic/'second-consistent-142-20261006/intent.json').read_text())
    expected=json.loads((original/'post-start-readonly-snapshot.json').read_text())
    old_expected=json.loads((historic/'second-consistent-142-20261006/source.json').read_text())
    final_expected=json.loads((historic/'rehearsal-a151/after.json').read_text())
    if expected['version']!='a0v_151':raise Maintenance151Blocked('REPAIR_ALREADY_MIGRATED151_REQUIRED')
    restore=_load('repair151_restore',ROOT/'scripts/a0v_current_150_restore_gate.py')
    primitive=_load('repair151_snapshot',ROOT/'scripts/a0v_current_142_restore_gate.py')
    maintenance=_load('repair151_process',ROOT/'scripts/a0v_current_142_maintenance.py')
    image=json.loads((historic/'second-consistent-142-20261006/restore-phase/intent.json').read_text())['image']
    state=ROOT.parent/('aos-recovery/current151-repair-'+secrets.token_hex(6));state.mkdir(mode=0o700)
    journal=Repair151Journal(state,head=head);journal._require_live_binding()
    source=restore.SOURCE_CONTAINER;target='current151-restore-'+secrets.token_hex(6)
    def inspect_source():
        journal._require_live_binding()
        item=json.loads(subprocess.check_output(['docker','--context',restore.SOURCE_CONTEXT,'inspect',source],timeout=30))[0]
        maintenance.require_source(item)
        if item['Id']!=source_identity['source_id'] or item['Image']!=source_identity['image']:raise Maintenance151Blocked('REPAIR_SOURCE_IDENTITY_DRIFT')
        return item
    def execute(name,args,data=None,check=True):
        journal._require_live_binding()
        context=restore.SOURCE_CONTEXT if name==source else restore.DEST_CONTEXT
        if name==source:
            require_current151_action(args);inspect_source()
        result=subprocess.run(['docker','--context',context]+args,input=data,capture_output=True,timeout=180)
        if check and result.returncode:raise Maintenance151Blocked('REPAIR_COMMAND_TERMINAL_'+str(result.returncode))
        return result
    def pg(name,statement,check=True):
        return execute(name,['exec','-i',name,'psql','-U','aos_app','-d',restore.SOURCE,'-Atq','-v','ON_ERROR_STOP=1','-f','-'],statement.encode(),check)
    def query(name,statement):
        return json.loads(pg(name,"BEGIN READ ONLY;SET LOCAL timezone='UTC';SET LOCAL search_path=pg_catalog,public;"+statement+';COMMIT;').stdout)
    def snapshot(name):return restore.full_snapshot(primitive,lambda q:query(name,q),expected['role_names'])
    def tenant_rows(name):
        return {t:query(name,"SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) AS value FROM public."+t+' t') for t in TENANT_TIMESTAMP_TABLES151}
    def metadata_rows(name):
        from psycopg import sql
        return {t:query(name,'SELECT json_agg(row_to_json(t) ORDER BY id) AS value FROM (SELECT * FROM public.'+t+' WHERE id IN ('+','.join(sql.Literal(x).as_string() for x in names)+')) t') for t,names in METADATA151_ADDITIONS.items()}
    def tcp_probe():
        import psycopg
        bootstrap=_load('repair151_connect',ROOT/'scripts/a0v_current_preview_bootstrap.py')
        params=bootstrap._connection_parameters()
        if (params['host'],params['port'],params['dbname'])!=('127.0.0.1',18435,restore.SOURCE):raise Maintenance151Blocked('REPAIR_TCP_IDENTITY_DRIFT')
        try:
            with psycopg.connect(**params,connect_timeout=3) as conn:
                conn.read_only=True;v=conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            if v!='a0v_151':raise Maintenance151Blocked('REPAIR_TCP_VERSION_DRIFT')
            return 0
        except psycopg.OperationalError:return 2
    def window():
        values=dict(listen_addresses=pg(source,'SHOW listen_addresses').stdout.decode().strip(),tcp_exit=tcp_probe(),other_clients=int(pg(source,"SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()").stdout),prepared=int(pg(source,'SELECT count(*) FROM pg_prepared_xacts').stdout))
        maintenance.require_window(**values);return values
    old_target=records['intent.json']['target']
    old_item=json.loads(subprocess.check_output(['docker','--context',restore.DEST_CONTEXT,'inspect',old_target]))[0]
    require_isolated151(old_item,name=old_target,image=image)
    if snapshot(old_target)['version']!='a0v_142':raise Maintenance151Blocked('ORIGINAL_WINDOW_RESTORE_VERSION_DRIFT')
    restore.require_dump_restore_equivalence(old_expected,snapshot(old_target))
    old_rows=tenant_rows(old_target);live_rows=tenant_rows(source)
    repair_sql=build_tenant_timestamp_repair151(old_rows,live_rows).as_string();repair_hash=hashlib.sha256(repair_sql.encode()).hexdigest()
    if snapshot(source)!=expected:raise Maintenance151Blocked('REPAIR_SOURCE_CHANGED_SINCE_FAILURE')
    corrected=copy.deepcopy(expected)
    for t in TENANT_TIMESTAMP_TABLES151:corrected['tables'][t]=old_expected['tables'][t]
    services=maintenance.current_services();previous=records['restart_clients-done.json']['result']['restarted']
    saved_services=json.loads((original/'services-original.json').read_text())
    for service in services:
        saved=next(x for x in saved_services if x['port']==service['port'])
        if any(service[k]!=saved[k] for k in ('argv','cwd','environment','helper_argv')):raise Maintenance151Blocked('REPAIR_SERVICE_COMMAND_DRIFT')
        prior=next(x['fingerprint'] for x in previous if x['port']==service['port']);now=service['fingerprint']
        if any(prior[k]!=now[k] for k in maintenance.PROCESS_FIELDS if k!='ppid'):raise Maintenance151Blocked('REPAIR_STARTED_PROCESS_DRIFT')
        if prior['ppid']!=now['ppid']:
            parent=subprocess.run(['ps','-p',str(prior['ppid']),'-o','stat='],capture_output=True,text=True)
            if parent.returncode==0 and not parent.stdout.strip().startswith('Z'):raise Maintenance151Blocked('ORIGINAL_WINDOW_PROCESS_STILL_ACTIVE')
    audit_restored151(base=historic,restore=restore,primitive=primitive)
    listen_query="SELECT json_agg(x) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x"
    listen_rows=query(source,listen_query);listen=pg(source,'SHOW listen_addresses').stdout.decode().strip()
    restore_statement=maintenance.listen_restore_statement(listen_rows,effective=listen)
    if tcp_probe()!=0:raise Maintenance151Blocked('REPAIR_TCP_BASELINE_REQUIRED')
    if read_task(thread=thread)!=task:raise Maintenance151Blocked('REPAIR_TASK_DRIFT')
    hashes={p.name:primitive.sha(p) for p in original.glob('*.json') if p.is_file()}
    journal._write('intent.json',dict(binding=journal.binding,original_window=str(original),original_hashes=hashes,source_id=source_identity['source_id'],source_image=source_identity['image'],source=source,target=target,image=image,repair_sql_sha256=repair_hash))
    journal._write('services-original.json',services)
    journal._write('listen-original.json',dict(rows=listen_rows,effective=listen,restore_statement=restore_statement))
    claim=ROOT.parent/'aos-recovery/current151-repair-claim-da8531053c83.json'
    try:fd=os.open(claim,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise Maintenance151Blocked('REPAIR_PHASE_EXISTS_RECONCILE_ONLY') from None
    with os.fdopen(fd,'w') as f:json.dump(dict(binding=journal.binding,state=str(state)),f);f.flush();os.fsync(f.fileno())
    fd=os.open(claim.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    journal.perform('reconcile',lambda:dict(status='verified',source_version='a0v_151',original_failed_window_bound=True))
    journal.perform('stop_clients',lambda:stop_services151(services,journal=journal,maintenance=maintenance))
    def fence():
        pg(source,"ALTER SYSTEM SET listen_addresses=''");execute(source,['restart',source])
        for _ in range(30):
            if execute(source,['exec',source,'pg_isready','-U','aos_app'],check=False).returncode==0:break
            time.sleep(1)
        return dict(status='verified',**window())
    journal.perform('fence_tcp',fence)
    def dump():
        window()
        if snapshot(source)!=expected:raise Maintenance151Blocked('REPAIR_WINDOW_SNAPSHOT_DRIFT')
        for filename,args in [('window.dump',['pg_dump','-U','aos_app','-d',restore.SOURCE,'-Fc']),('window-globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
            data=execute(source,['exec',source]+args).stdout
            with os.fdopen(os.open(state/filename,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        return dict(status='verified',dump_sha256=primitive.sha(state/'window.dump'),globals_sha256=primitive.sha(state/'window-globals.sql'))
    journal.perform('snapshot_dump',dump)
    def independent_restore():
        window()
        execute(target,['run','-d','--pull','never','--name',target,'--network','none','--cpus','1','--memory','768m','--mount','type=volume,source='+target+'-data,target=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image])
        for _ in range(30):
            if execute(target,['exec',target,'pg_isready','-U','aos_app'],check=False).returncode==0:break
            time.sleep(1)
        item=json.loads(execute(target,['inspect',target]).stdout)[0];require_isolated151(item,name=target,image=image)
        globals_data=primitive.prepare_globals((state/'window-globals.sql').read_bytes(),bootstrap='aos_app')
        execute(target,['exec','-i',target,'psql','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],globals_data)
        execute(target,['exec','-i',target,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],(state/'window.dump').read_bytes())
        restore.require_dump_restore_equivalence(expected,snapshot(target))
        return dict(status='verified',tables=len(expected['tables']),schema='a0v_151')
    journal.perform('independent_restore',independent_restore)
    def rehearse():
        window()
        data=build_tenant_timestamp_repair151(old_rows,tenant_rows(target)).as_string()
        if data!=repair_sql:raise Maintenance151Blocked('REPAIR_SQL_REHEARSAL_DRIFT')
        r=pg(target,data,check=False);journal._write('rehearsal-terminal.json',dict(exit_code=r.returncode,sql_sha256=repair_hash))
        if r.returncode:raise Maintenance151Blocked('REPAIR_REHEARSAL_TERMINAL_FAILURE')
        restore.require_dump_restore_equivalence(corrected,snapshot(target))
        return dict(status='verified',sql_sha256=repair_hash,full_snapshot=True)
    journal.perform('rehearse_repair',rehearse)
    def repair():
        window()
        if snapshot(source)!=expected or tenant_rows(source)!=live_rows:raise Maintenance151Blocked('REPAIR_PRE_CAS_DRIFT')
        r=pg(source,repair_sql,check=False);journal._write('repair-terminal.json',dict(exit_code=r.returncode,sql_sha256=repair_hash))
        if r.returncode:raise Maintenance151Blocked('REPAIR_CAS_TERMINAL_FAILURE_RECONCILE_ONLY')
        return dict(status='verified',sql_sha256=repair_hash)
    journal.perform('repair_timestamps',repair)
    template_rows=metadata_rows(json.loads((historic/'same-image-phase/intent.json').read_text())['container'])
    def verify():
        observed=snapshot(source)
        if observed!=corrected:raise Maintenance151Blocked('REPAIRED_CURRENT_FULL_SNAPSHOT_DRIFT')
        normalized=normalize_metadata151(old_expected,final_expected,observed,template_rows,metadata_rows(source))
        restore.require_dump_restore_equivalence(final_expected,normalized)
        require_withdrawal_fence(ReadOnlyCatalogConnection(lambda q:query(source,q)))
        return dict(status='verified',all_old_rows_preserved=True,withdrawal_fence='exact')
    journal.perform('verify',lambda:(window(),verify())[1])
    def restore_tcp():
        pg(source,restore_statement);execute(source,['restart',source])
        for _ in range(30):
            if execute(source,['exec',source,'pg_isready','-U','aos_app'],check=False).returncode==0:break
            time.sleep(1)
        if tcp_probe()!=0 or query(source,listen_query)!=listen_rows:raise Maintenance151Blocked('REPAIR_LISTEN_RESTORE_DRIFT')
        return dict(status='verified',original_config_restored=True)
    journal.perform('restore_tcp',restore_tcp)
    journal.perform('restart_clients',lambda:restart_services151(services,journal=journal,maintenance=maintenance))
    journal.perform('acceptance',verify)
    report=dict(outcome='CURRENT151_REPAIR_SERVICES_GREEN_BROWSER_PENDING',state=str(state),head=head,schema='a0v_151',old_timestamps_restored=True,business_first_chain=False)
    journal._write('result.json',report)
    return report
