"""Current-142 full backup and isolated exact restore, before 150 rehearsal.

This phase has no source migration, service control, LOGIN provisioning or
business execution. Later rehearsal and maintenance remain separate gates.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
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
CATALOG_KEYS=frozenset(('columns','constraints','indexes','triggers','column_acl','relation_acl',
    'schema_acl','function_acl','views','types','extensions','default_acl','event_triggers'))


class Restore150Blocked(RuntimeError):
    pass


def require(value,reason):
    if not value:raise Restore150Blocked(reason)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def bound_image(source,target,binding):
    require(source['Id']==binding['source_config_id'] and target['Id']==binding['target_manifest_id']
        and re.fullmatch(r'sha256:[0-9a-f]{64}',target['Id']) is not None,'IMAGE_NATIVE_IDENTITY_DRIFT')
    for key in ('Config','RootFS','Architecture','Os'):
        require(source[key]==target[key],'IMAGE_CONTENT_DRIFT_'+key)
    for key,label in (('Config','config_hash'),('RootFS','rootfs_hash')):
        require(hashlib.sha256(json.dumps(source[key],sort_keys=True).encode()).hexdigest()==binding[label],
            'IMAGE_BINDING_HASH_DRIFT')
    return target['Id']


def isolated_source_image(inspect,source_id):
    parent=ROOT.parent/'aos-recovery/current150-source-image-20261006'
    require_private_parent(parent)
    path=parent/'image-binding.json';info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid()
        and stat.S_IMODE(info.st_mode)==0o600,'IMAGE_BINDING_FILE_DRIFT')
    binding=json.loads(path.read_text())
    require(source_id==binding['source_config_id'],'SOURCE_IMAGE_BINDING_DRIFT')
    return bound_image(inspect(SOURCE_CONTEXT,source_id),inspect(DEST_CONTEXT,binding['target_manifest_id']),binding)


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


def length_and_candidate(definition):
    """Diagnostic candidate only; never used by the exact restore gate."""
    match=re.fullmatch(r'CHECK \(\(\(\(length\(([a-z_]+)\) >= 1\) AND \(length\(\1\) <= (160|240)\)\) AND (.+)\)\)',definition)
    if match is None:return definition
    column,bound,tail=match.groups()
    trim=f'({column} = btrim({column}))'
    control=f"({column} !~ '[[:cntrl:]]'::text)"
    allowed={trim,trim+' AND '+control}
    if column=='operation_id' and bound=='160':
        allowed.add("(operation_id ~ '^[A-Za-z][A-Za-z0-9_]*$'::text)")
    if tail not in allowed:return definition
    return f'CHECK (((length({column}) >= 1) AND (length({column}) <= {bound}) AND {tail}))'


def require_exact_restore(before,after):
    for value in (before,after):
        require(type(value.get('full_catalog')) is dict and set(value['full_catalog'])==CATALOG_KEYS
            and all(type(rows) is list for rows in value['full_catalog'].values()),'FULL_CATALOG_COVERAGE_REQUIRED')
    require(before==after,'FULL_RESTORE_STATE_MISMATCH')


def require_dump_restore_equivalence(before,after):
    """Only reviewed CHECK conjunction reassociation; every other field exact."""
    left,right=copy.deepcopy(before),copy.deepcopy(after)
    for value in (left,right):
        require(type(value.get('full_catalog')) is dict and set(value['full_catalog'])==CATALOG_KEYS
            and all(type(rows) is list for rows in value['full_catalog'].values()),'FULL_CATALOG_COVERAGE_REQUIRED')
    changed=[]
    for value in (left,right):
        for row in value['full_catalog']['constraints']:
            if row['contype']!='c':continue
            normalized=length_and_candidate(row['definition'])
            if normalized!=row['definition']:
                changed.append(row['relation']+'.'+row['conname'])
                row['definition']=normalized
    require_exact_restore(left,right)
    return sorted(set(changed))


def require_supported_schemas(schemas):
    require(schemas==['public'],'UNSUPPORTED_USER_SCHEMA')


def require_private_parent(parent):
    parent=Path(parent)
    require(parent.is_absolute(),'PRIVATE_PARENT_ABSOLUTE_REQUIRED')
    for ancestor in [*reversed(parent.parents),parent]:
        info=ancestor.lstat()
        require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode)
            and info.st_uid in {0,os.getuid()},'PRIVATE_PARENT_PATH_DRIFT')
    info=parent.lstat()
    require(info.st_uid==os.getuid() and not stat.S_IMODE(info.st_mode)&0o022,'PRIVATE_PARENT_WRITABLE_BY_OTHERS')


def require_source_identity(before,after):
    require(all(before[key]==after[key] for key in ('Id','Image')),'SOURCE_CONTAINER_OR_IMAGE_CHANGED')


def require_supported_relations(kinds):
    require(type(kinds) is list and all(kind in {'r','i','S'} for kind in kinds),
        'UNSUPPORTED_RELATION_KIND')


def full_snapshot(g,query,roles=None):
    require_supported_relations(query("SELECT coalesce(json_agg(kind ORDER BY kind),'[]') AS value FROM "
        "(SELECT DISTINCT c.relkind::text AS kind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema') kinds"))
    require_supported_schemas(query("SELECT coalesce(json_agg(nspname ORDER BY nspname),'[]') AS value "
        "FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname<>'information_schema'"))
    result=g.snapshot(query,roles)
    specs={
        'columns':"SELECT c.relname AS relation,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod) AS type,"
            "a.attnotnull,a.attidentity,a.attgenerated,a.attstorage,a.attcompression,a.attstattarget,"
            "pg_get_expr(d.adbin,d.adrelid) AS default_expr,co.collname AS collation "
            "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum LEFT JOIN pg_collation co ON co.oid=a.attcollation "
            "WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped",
        'constraints':"SELECT c.relname AS relation,k.conname,k.contype,k.convalidated,k.condeferrable,k.condeferred,"
            "pg_get_constraintdef(k.oid) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'",
        'indexes':"SELECT c.relname AS relation,i.relname AS name,x.indisvalid,x.indisready,x.indislive,"
            "pg_get_indexdef(i.oid) AS definition FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid "
            "JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'",
        'triggers':"SELECT c.relname AS relation,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) AS definition "
            "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND NOT t.tgisinternal",
        'column_acl':"SELECT c.relname AS relation,a.attname,pg_get_userbyid(x.grantor) AS grantor,"
            "CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,"
            "x.privilege_type,x.is_grantable FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname='public'",
        'relation_acl':"SELECT c.relname AS relation,pg_get_userbyid(x.grantor) AS grantor,"
            "CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN LATERAL "
            "aclexplode(coalesce(c.relacl,acldefault((CASE WHEN c.relkind='S' THEN 'S' ELSE 'r' END)::\"char\",c.relowner))) x "
            "WHERE n.nspname='public'",
        'schema_acl':"SELECT n.nspname,pg_get_userbyid(n.nspowner) AS owner,pg_get_userbyid(x.grantor) AS grantor,"
            "CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,x.privilege_type,x.is_grantable "
            "FROM pg_namespace n CROSS JOIN LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) x WHERE n.nspname='public'",
        'function_acl':"SELECT p.proname||'('||pg_get_function_identity_arguments(p.oid)||')' AS name,"
            "pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,"
            "x.privilege_type,x.is_grantable FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) x WHERE n.nspname='public'",
        'views':"SELECT c.relname AS name,c.relkind,pg_get_viewdef(c.oid) AS definition FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN('v','m')",
        'types':"SELECT t.typname,t.typtype,pg_get_userbyid(t.typowner) AS owner,format_type(t.typbasetype,t.typtypmod) AS base_type,"
            "t.typnotnull,t.typdefault,(SELECT json_agg(e.enumlabel ORDER BY e.enumsortorder) FROM pg_enum e WHERE e.enumtypid=t.oid) AS labels "
            "FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typtype IN('d','e')",
        'extensions':"SELECT e.extname,e.extversion,pg_get_userbyid(e.extowner) AS owner,n.nspname,e.extrelocatable "
            "FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace",
        'default_acl':"SELECT pg_get_userbyid(a.defaclrole) AS owner,coalesce(n.nspname,'GLOBAL') AS schema,a.defaclobjtype,"
            "pg_get_userbyid(x.grantor) AS grantor,CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END AS grantee,"
            "x.privilege_type,x.is_grantable FROM pg_default_acl a LEFT JOIN pg_namespace n ON n.oid=a.defaclnamespace "
            "CROSS JOIN LATERAL aclexplode(a.defaclacl) x",
        'event_triggers':"SELECT evtname,evtevent,pg_get_userbyid(evtowner) AS owner,evtfoid::regprocedure::text AS function,"
            "evtenabled,evttags FROM pg_event_trigger",
    }
    catalog={}
    for name,statement in specs.items():
        # JSON objects have no OIDs; sorting canonical row JSON avoids unstable
        # restore-generated identifiers and input ACL array order.
        catalog[name]=query("SELECT coalesce(json_agg(value ORDER BY value::text),'[]') AS value "
            "FROM (SELECT row_to_json(x) AS value FROM ("+statement+") x) rows")
    result['full_catalog']=catalog
    return result


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
    require_private_parent(ROOT.parent/'aos-recovery')
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
        image=isolated_source_image(inspect,source_item['Image'])
        container='current150-'+secrets.token_hex(6)
        g.save(state/'intent.json',dict(head=head,revision=revision,source=SOURCE,source_version='a0v_142',
            source_context=SOURCE_CONTEXT,source_volume=SOURCE_VOLUME,source_id=source_item['Id'],source_image=source_item['Image'],
            container=container,volume=container+'-data',image=image,destination_context=DEST_CONTEXT,
            authorization='FULL_BACKUP_EXACT_RESTORE_ONLY_NO_CURRENT_MUTATION'))
        stage='consistent_full_backup'
        with psycopg.connect(**parameters,row_factory=dict_row) as conn:
            conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            before=full_snapshot(g,lambda statement:conn.execute(statement).fetchone()['value'])
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
        restored=full_snapshot(g,query,before['role_names'])
        require_exact_restore(before,restored)
        g.save(state/'restored.json',restored)
        with psycopg.connect(**parameters,row_factory=dict_row) as conn:
            conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
            conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
            require_exact_restore(before,full_snapshot(g,lambda statement:conn.execute(statement).fetchone()['value']))
        final_source=inspect(SOURCE_CONTEXT,SOURCE_CONTAINER)
        maintenance.require_source(final_source);require_source_identity(source_item,final_source)
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


def reconcile_catalog():
    """Read the original backup/clone only; never reissue dump or restoration."""
    revision=read_task();require_private_parent(ROOT.parent/'aos-recovery')
    state=ROOT.parent/'aos-recovery'/('current150-'+TASK)
    require_private_parent(state)
    g=load('restore142_reconcile_primitives',ROOT/'scripts/a0v_current_142_restore_gate.py')
    original=json.loads((state/'intent.json').read_text())
    completed=json.loads((state/'result.json').read_text())
    backup=json.loads((state/'backup.json').read_text())
    require(completed['head']==original['head'] and completed['container']==original['container']
        and completed['restored_version']=='a0v_142','ORIGINAL_RESTORE_IDENTITY_DRIFT')
    require(g.sha(state/'current-full.dump')==backup['sha256']
        and g.sha(state/'globals-no-password.sql')==backup['globals_sha256'],'ORIGINAL_BACKUP_HASH_DRIFT')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    def inspect(context,name):
        raw=subprocess.check_output(['docker','--context',context,'inspect',name])
        return json.loads(raw)[0]
    source_item=inspect(SOURCE_CONTEXT,SOURCE_CONTAINER)
    maintenance=load('current150_reconcile_identity',ROOT/'scripts/a0v_current_142_maintenance.py')
    maintenance.require_source(source_item)
    require(source_item['Image']==original['source_image'],'ORIGINAL_SOURCE_IMAGE_DRIFT')
    target_item=inspect(DEST_CONTEXT,original['container'])
    require_target(target_item,container=original['container'],image=original['image'])
    bootstrap=load('current150_reconcile_bootstrap',ROOT/'scripts/a0v_current_preview_bootstrap.py')
    parameters=bootstrap._connection_parameters()
    require((parameters['host'],parameters['port'],parameters['dbname'],parameters['user'])
        ==('127.0.0.1',18435,SOURCE,'aos_app'),'EXACT_CURRENT_SOURCE_REQUIRED')
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
        conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
        source=full_snapshot(g,lambda statement:conn.execute(statement).fetchone()['value'])
    recorded=json.loads((state/'source.json').read_text())
    require({key:value for key,value in source.items() if key!='full_catalog'}==recorded,
        'ORIGINAL_SOURCE_SNAPSHOT_CHANGED')
    def query(statement):
        raw=subprocess.check_output(['docker','--context',DEST_CONTEXT,'exec',original['container'],
            'psql','-U','aos_app','-d',SOURCE,'-v','ON_ERROR_STOP=1','-Atq','-c',
            "BEGIN READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; "+statement+'; COMMIT'],timeout=300)
        return json.loads(raw)
    clone=full_snapshot(g,query,source['role_names'])
    require_exact_restore(source,clone)
    require_source_identity(source_item,inspect(SOURCE_CONTEXT,SOURCE_CONTAINER))
    require_source_identity(target_item,inspect(DEST_CONTEXT,original['container']))
    require(read_task()==revision and subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head,
        'RECONCILIATION_BASELINE_DRIFT')
    g.save(state/'catalog-source.json',source);g.save(state/'catalog-restored.json',clone)
    result=dict(outcome='EXISTING_BACKUP_FULL_CATALOG_RECONCILIATION_GREEN_REHEARSAL_PENDING',
        original_head=original['head'],head=head,source_version=source['version'],restored_version=clone['version'],
        old_tables=len(source['tables']),catalog_rows={key:len(rows) for key,rows in source['full_catalog'].items()},
        source_id=source_item['Id'],source_image=source_item['Image'],source_identity_fixed_during_reconciliation=True,
        original_capture_source_id_recorded='source_id' in original,original_comparison_superseded=True,
        backup_sha256=backup['sha256'],container=original['container'],state=str(state),source_mutations=0,
        migration_rehearsed=False,services_stopped=False)
    g.save(state/'catalog-reconciliation.json',result)
    return result


def restore_same_image_target():
    """Known terminal 16.15 comparison failed; restore preserved backup at 16.14."""
    revision=read_task();require_private_parent(ROOT.parent/'aos-recovery')
    state=ROOT.parent/'aos-recovery'/('current150-'+TASK);require_private_parent(state)
    g=load('same_image142_primitives',ROOT/'scripts/a0v_current_142_restore_gate.py')
    original=json.loads((state/'intent.json').read_text());completed=json.loads((state/'result.json').read_text())
    backup=json.loads((state/'backup.json').read_text())
    require(completed['restored_version']=='a0v_142' and completed['container']==original['container'],
        'ORIGINAL_RESTORE_NOT_KNOWN_TERMINAL')
    require(g.sha(state/'current-full.dump')==backup['sha256']
        and g.sha(state/'globals-no-password.sql')==backup['globals_sha256'],'ORIGINAL_BACKUP_HASH_DRIFT')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    phase=state/'same-image-phase';phase.mkdir(mode=0o700)
    def guard():
        require(read_task()==revision and subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==head,
            'SAME_IMAGE_RESTORE_BASELINE_DRIFT')
    def execute(args,data=None):
        guard()
        result=subprocess.run(['docker','--context',DEST_CONTEXT,*args],input=data,capture_output=True,timeout=300)
        require(result.returncode==0,'SAME_IMAGE_RESTORE_STEP_FAILED')
        return result.stdout
    def inspect(context,name):
        return json.loads(subprocess.check_output(['docker','--context',context,'inspect',name]))[0]
    source_item=inspect(SOURCE_CONTEXT,SOURCE_CONTAINER)
    maintenance=load('same_image_current_identity',ROOT/'scripts/a0v_current_142_maintenance.py');maintenance.require_source(source_item)
    require(source_item['Image']==original['source_image'],'ORIGINAL_SOURCE_IMAGE_CHANGED')
    image=isolated_source_image(inspect,source_item['Image'])
    bootstrap=load('same_image_bootstrap',ROOT/'scripts/a0v_current_preview_bootstrap.py')
    parameters=bootstrap._connection_parameters()
    require((parameters['host'],parameters['port'],parameters['dbname'],parameters['user'])
        ==('127.0.0.1',18435,SOURCE,'aos_app'),'EXACT_CURRENT_SOURCE_REQUIRED')
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
        conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
        before=full_snapshot(g,lambda statement:conn.execute(statement).fetchone()['value'])
    recorded=json.loads((state/'source.json').read_text())
    require({key:value for key,value in before.items() if key!='full_catalog'}==recorded,'ORIGINAL_SOURCE_SNAPSHOT_CHANGED')
    container='current150-same-'+secrets.token_hex(6)
    g.save(phase/'intent.json',dict(head=head,revision=revision,container=container,volume=container+'-data',image=image,
        source_id=source_item['Id'],source_image=source_item['Image'],backup_sha256=backup['sha256'],original_target_preserved=original['container']))
    execute(['run','-d','--pull','never','--name',container,'--label','aos.restore-gate=20261005-150','--network','none',
        '--cpus','1','--memory','768m','--mount','type=volume,source='+container+'-data,target=/var/lib/postgresql/data',
        '-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image])
    require_target(inspect(DEST_CONTEXT,container),container=container,image=image)
    for _ in range(30):
        ready=subprocess.run(['docker','--context',DEST_CONTEXT,'exec',container,'pg_isready','-U','aos_app','-d','postgres'],capture_output=True)
        if ready.returncode==0:break
        time.sleep(1)
    else:raise Restore150Blocked('SAME_IMAGE_TARGET_NOT_READY')
    execute(['exec','-i',container,'psql','-U','aos_app','-d','postgres','-v','ON_ERROR_STOP=1','-q','-f','-'],
        g.prepare_globals((state/'globals-no-password.sql').read_bytes(),bootstrap='aos_app'))
    execute(['exec','-i',container,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],
        (state/'current-full.dump').read_bytes())
    def query(statement):
        return json.loads(execute(['exec',container,'psql','-U','aos_app','-d',SOURCE,'-v','ON_ERROR_STOP=1','-Atq','-c',
            "BEGIN READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public; "+statement+'; COMMIT']))
    restored=full_snapshot(g,query,before['role_names']);require_exact_restore(before,restored)
    with psycopg.connect(**parameters,row_factory=dict_row) as conn:
        conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;conn.read_only=True
        conn.execute("SET LOCAL timezone='UTC'; SET LOCAL search_path=pg_catalog,public")
        require_exact_restore(before,full_snapshot(g,lambda statement:conn.execute(statement).fetchone()['value']))
    final_source=inspect(SOURCE_CONTEXT,SOURCE_CONTAINER);maintenance.require_source(final_source)
    require_source_identity(source_item,final_source);require_target(inspect(DEST_CONTEXT,container),container=container,image=image);guard()
    g.save(phase/'source.json',before);g.save(phase/'restored.json',restored)
    result=dict(outcome='SAME_IMAGE_FULL_CATALOG_RESTORE_GREEN_REHEARSAL_PENDING',head=head,source_version=before['version'],
        restored_version=restored['version'],old_tables=len(before['tables']),catalog_rows={key:len(rows) for key,rows in before['full_catalog'].items()},
        container=container,volume=container+'-data',image=image,state=str(phase),original_backup_sha256=backup['sha256'],
        original_target_preserved=True,source_mutations=0,services_stopped=False,migration_rehearsed=False)
    g.save(phase/'result.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['capture-restore','reconcile-catalog','restore-same-image']);args=parser.parse_args()
    try:print(json.dumps({'capture-restore':capture_and_restore,'reconcile-catalog':reconcile_catalog,
        'restore-same-image':restore_same_image_target}[args.command](),ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(dict(outcome='RESTORE_NOT_GREEN',error_type=type(exc).__name__)))
        raise SystemExit(1)
