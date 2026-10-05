"""Current-142 full backup and isolated exact restore, before 150 rehearsal.

This phase has no source migration, service control, LOGIN provisioning or
business execution. Later rehearsal and maintenance remain separate gates.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time

import psycopg
from psycopg.rows import dict_row
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT=Path(__file__).resolve().parents[1]
TASK='w5cb4-current150-restore-gate-20261005-154201'
OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
SOURCE='aos_current_preview_20260927'
SOURCE_CONTEXT='colima-aos-extension'
SOURCE_CONTAINER='aos-a0v-recovery-pg'
SOURCE_VOLUME='aos-a0v-recovery-pg-data'
DEST_CONTEXT='colima-aos-a0v-test-only'


class Restore150Blocked(RuntimeError):
    pass


def require(value,reason):
    if not value:raise Restore150Blocked(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def require_target(item,*,container,image):
    require(re.fullmatch(r'current150-[a-z0-9-]+',container) is not None,'DEST_NAME_REQUIRED')
    require(item['Name']=='/'+container and item['State']['Running'],'DEST_IDENTITY_DRIFT')
    require(item['Image']==image and item['Config']['Labels'].get('aos.restore-gate')=='20261005-150','DEST_IMAGE_DRIFT')
    require(item['HostConfig']['NetworkMode']=='none' and not item['HostConfig']['Privileged'],'DEST_NETWORK_DRIFT')
    require(not any(item['NetworkSettings']['Ports'].values()),'DEST_PORT_FORBIDDEN')
    require(len(item['Mounts'])==1 and item['Mounts'][0]['Type']=='volume'
            and item['Mounts'][0].get('Name')==container+'-data'
            and item['Mounts'][0]['Name']!=SOURCE_VOLUME
            and item['Mounts'][0]['Destination']=='/var/lib/postgresql/data'
            and item['Mounts'][0]['RW'] is True,'DEST_MOUNT_DRIFT')


def require_exact_restore(before,after):
    require(before==after,'FULL_RESTORE_STATE_MISMATCH')


def read_task():
    memory=ROOT.parent/'docs/palantier/AOS项目开发上下文/memory'
    authority=json.loads((memory/'authority.json').read_text())
    task=json.loads((memory/'receipts/tasks'/f'{TASK}.json').read_text())
    leases=json.loads((memory/'leases.json').read_text())['leases']
    require(task['task_id']==TASK and task['owner']==OWNER and task['status']=='ACTIVE'
        and task['base_revision']=='AOS-001356','RESTORE_TASK_IDENTITY_DRIFT')
    require(not (memory/'receipts/deliveries'/f'{TASK}.json').exists(),'RESTORE_TASK_ALREADY_DELIVERED')
    require([lease for lease in leases if lease['task_id']==TASK]==[task],'RESTORE_LEASE_DRIFT')
    require(datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc),'RESTORE_LEASE_EXPIRED')
    require({'aos-recovery/current150-*','isolatedDocker:colima-aos-a0v-test-only/current150-*'}<=set(task['scope']),
        'RESTORE_RESOURCE_SCOPE_MISSING')
    return authority['project_revision']


def capture_and_restore():
    require(not os.environ.get('AOS_DATABASE_URL'),'AMBIENT_DATABASE_FORBIDDEN')
    revision=read_task()
    require(subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()=='m1','M1_REQUIRED')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    config=Config(str(ROOT/'services/aos-api/alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'services/aos-api/alembic'))
    require(ScriptDirectory.from_config(config).get_heads()==['a0v_150'],'EXACT_CODE_150_REQUIRED')
    g=load('restore142_primitives',ROOT/'scripts/a0v_current_142_restore_gate.py')
    maintenance=load('source142_identity',ROOT/'scripts/a0v_current_142_maintenance.py')
    bootstrap=load('current150_bootstrap',ROOT/'scripts/a0v_current_preview_bootstrap.py')
    parameters=bootstrap._connection_parameters()
    require((parameters['host'],parameters['port'],parameters['dbname'],parameters['user'])
        ==('127.0.0.1',18435,SOURCE,'aos_app'),'EXACT_CURRENT_SOURCE_REQUIRED')
    state=ROOT.parent/'aos-recovery'/('current150-'+TASK)
    state.mkdir(mode=0o700)  # Existing intent must be reconciled, never overwritten.
    stage='preflight';started=time.monotonic()

    def guard():
        require(read_task()==revision,'AUTHORITY_CHANGED_DURING_RESTORE')
        require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head,'CODE_HEAD_DRIFT')

    def command(context,args,*,data=None,path=None):
        guard()
        if context==SOURCE_CONTEXT:
            require(args[0]=='exec' and SOURCE_CONTAINER in args,'SOURCE_MUTATION_FORBIDDEN')
            executable=args[args.index(SOURCE_CONTAINER)+1]
            require(executable in {'pg_dump','pg_dumpall','pg_restore'},'SOURCE_COMMAND_FORBIDDEN')
            if executable=='pg_restore':require('--list' in args,'SOURCE_RESTORE_FORBIDDEN')
        result=subprocess.run(['docker','--context',context,*args],input=data,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300)
        require(result.returncode==0,'DOCKER_STEP_FAILED_'+stage)
        if path is not None:
            with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
                f.write(result.stdout);f.flush();os.fsync(f.fileno())
        return result.stdout

    def inspect(context,name):
        guard()
        result=subprocess.run(['docker','--context',context,'inspect',name],capture_output=True,check=True,timeout=30)
        return json.loads(result.stdout)[0]

    try:
        source_item=inspect(SOURCE_CONTEXT,SOURCE_CONTAINER)
        maintenance.require_source(source_item)
        image=inspect(DEST_CONTEXT,'aos-sequence142-432d8abc48e2')['Image']
        container='current150-'+secrets.token_hex(6)
        g.save(state/'intent.json',dict(head=head,revision=revision,source=SOURCE,source_version='a0v_142',
            source_context=SOURCE_CONTEXT,source_volume=SOURCE_VOLUME,source_image=source_item['Image'],
            container=container,volume=container+'-data',image=image,destination_context=DEST_CONTEXT,
            authorization='FULL_BACKUP_EXACT_RESTORE_ONLY_NO_CURRENT_MUTATION'))
        stage='consistent_full_backup'
        with psycopg.connect(**parameters,row_factory=dict_row) as conn:
            conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            before=g.snapshot(lambda statement:conn.execute(statement).fetchone()['value'])
            require(before['version']=='a0v_142','EXACT_SOURCE_142_REQUIRED')
            snapshot_id=conn.execute('SELECT pg_export_snapshot() AS id').fetchone()['id']
            command(SOURCE_CONTEXT,['exec',SOURCE_CONTAINER,'pg_dump','-U','aos_app','-d',SOURCE,'-Fc','--snapshot',snapshot_id],
                path=state/'current-full.dump')
        g.save(state/'source.json',before)
        command(SOURCE_CONTEXT,['exec',SOURCE_CONTAINER,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'],
            path=state/'globals-no-password.sql')
        globals_data=(state/'globals-no-password.sql').read_bytes()
        require(b'CREATE TABLESPACE' not in globals_data,'CUSTOM_TABLESPACE_REQUIRES_PLAN')
        restore_globals=g.prepare_globals(globals_data,bootstrap='aos_app')
        toc=command(SOURCE_CONTEXT,['exec','-i',SOURCE_CONTAINER,'pg_restore','--list'],data=(state/'current-full.dump').read_bytes())
        require(b'TABLE DATA' in toc,'BACKUP_TOC_INVALID')
        g.save(state/'backup.json',dict(bytes=(state/'current-full.dump').stat().st_size,
            sha256=g.sha(state/'current-full.dump'),globals_sha256=g.sha(state/'globals-no-password.sql'),toc_lines=len(toc.splitlines())))
        stage='create_independent_target'
        command(DEST_CONTEXT,['run','-d','--pull','never','--name',container,'--label','aos.restore-gate=20261005-150',
            '--network','none','--cpus','1','--memory','768m','--mount','type=volume,source='+container+'-data,target=/var/lib/postgresql/data',
            '-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image])
        require_target(inspect(DEST_CONTEXT,container),container=container,image=image)
        for _ in range(30):
            ready=subprocess.run(['docker','--context',DEST_CONTEXT,'exec',container,'pg_isready','-U','aos_app','-d','postgres'],capture_output=True)
            if ready.returncode==0:break
            time.sleep(1)
        else:raise Restore150Blocked('DEST_NOT_READY')
        stage='restore_globals_and_database'
        command(DEST_CONTEXT,['exec','-i',container,'psql','-U','aos_app','-d','postgres','-v','ON_ERROR_STOP=1','-q','-f','-'],data=restore_globals)
        command(DEST_CONTEXT,['exec','-i',container,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],
            data=(state/'current-full.dump').read_bytes())
        stage='exact_restore_compare'
        def query(statement):
            raw=command(DEST_CONTEXT,['exec',container,'psql','-U','aos_app','-d',SOURCE,'-v','ON_ERROR_STOP=1','-Atq','-c',
                "BEGIN READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; "+statement+'; COMMIT'])
            return json.loads(raw)
        restored=g.snapshot(query,before['role_names'])
        require_exact_restore(before,restored)
        g.save(state/'restored.json',restored)
        with psycopg.connect(**parameters,row_factory=dict_row) as conn:
            conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            require_exact_restore(before,g.snapshot(lambda statement:conn.execute(statement).fetchone()['value']))
        maintenance.require_source(inspect(SOURCE_CONTEXT,SOURCE_CONTAINER))
        guard()
        result=dict(outcome='CURRENT142_FULL_BACKUP_EXACT_RESTORE_GREEN_REHEARSAL_PENDING',head=head,revision=revision,
            source_version='a0v_142',restored_version='a0v_142',old_tables=len(before['tables']),state=str(state),
            container=container,volume=container+'-data',seconds=round(time.monotonic()-started,3),
            source_mutations=0,services_stopped=False,migration_rehearsed=False)
        g.save(state/'result.json',result)
        return result
    except Exception as exc:
        g.save(state/'failure.json',dict(stage=stage,error_type=type(exc).__name__,unknown_reconcile_original_only=True))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['capture-restore']);parser.parse_args()
    try:print(json.dumps(capture_and_restore(),ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(dict(outcome='RESTORE_NOT_GREEN',error_type=type(exc).__name__)))
        raise SystemExit(1)
