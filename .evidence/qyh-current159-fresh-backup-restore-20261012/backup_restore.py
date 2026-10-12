"""Fresh current-volume backup and full restore confined to a new owned clone DB."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import psycopg
from psycopg import sql

OUT=Path(__file__).parent
ROOT=OUT.parents[1]
SOURCE='qyh-restored-pg-20261011'
CLONE='qyh-source-boundary-clone-20261011'
CONTEXT='colima-aos-extension'
DATABASE='qyh_current159_restore_20261012'


def record(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False)


def current_sql(query):
    return subprocess.check_output(['docker','--context',CONTEXT,'exec','-i',SOURCE,
        'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d','aos_meta_head'],
        input='BEGIN READ ONLY; '+query+' COMMIT;',text=True)


def source_fingerprint():
    tables=json.loads(current_sql("SELECT json_agg(json_build_object('schema',n.nspname,'name',c.relname) ORDER BY n.nspname,c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';"))
    queries=[]
    for t in tables:
        qualified='.'.join('"'+t[k].replace('"','""')+'"' for k in ('schema','name'))
        key=(t['schema']+'.'+t['name']).replace("'","''")
        queries.append("SELECT '"+key+"' AS name,count(*) AS rows,encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS hash FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM "+qualified+" t) q")
    result=json.loads(current_sql("SELECT json_agg(row_to_json(x)) FROM ("+' UNION ALL '.join(queries)+") x;"))
    return {r['name']:{'rows':r['rows'],'hash':r['hash']} for r in result}


if __name__=='__main__':
    assert not (OUT/'intent.json').exists(), 'Existing attempt: reconcile read-only, do not resend'
    spec=importlib.util.spec_from_file_location('rehearse',ROOT/'.evidence/qyh-head160-restoration-rehearsal-20261012/inspect_rehearse.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    source=previous.container(SOURCE);clone=previous.container(CLONE)
    assert source['Running'] and len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
    assert source['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18446'}]
    assert clone['Id']=='381ac0fd489c72a5cad26a962dd59ba749d027bb61ab779703d1eb4bdb197b93' and clone['Running'] and not clone['Mounts']
    assert clone['Image']==source['Image']=='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
    meta=json.loads(current_sql("""SELECT json_build_object(
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'schema',(SELECT version_num FROM alembic_version),
      'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),
      'otherClients',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'),
      'otherActiveClients',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend' AND state='active'));"""))
    assert meta['cluster']=='7695302940039200809' and meta['schema']=='a0v_159' and meta['enabledBindings']==0
    record('current-window-observation.json',{**meta,'continuousZeroExecutionWindowProven':False,'actualDatabaseWrites':0})
    before=source_fingerprint();assert len(before)==647
    record('current-baseline.json',before)
    private=OUT/'private';private.mkdir(mode=0o700)
    backup=private/'current.dump';copydir=private/'copy';copydir.mkdir(mode=0o700)
    record('intent.json',{'sourceVolume':source['Mounts'][0]['Name'],'database':'aos_meta_head','version':'a0v_159',
        'backupPath':str(backup),'ownedRestoreDatabase':DATABASE,'actualDatabaseMigration':False})
    fd=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:
        dump=subprocess.run(['docker','--context',CONTEXT,'exec',SOURCE,'pg_dump','-Fc','-U','aos_app','-d','aos_meta_head'],stdout=f,stderr=subprocess.PIPE)
    assert dump.returncode==0, 'Backup failed: diagnose exact local artifact, never migrate'
    backup_hash=hashlib.sha256(backup.read_bytes()).hexdigest()
    second=copydir/'current.dump';shutil.copyfile(backup,second);second.chmod(0o600)
    assert hashlib.sha256(second.read_bytes()).hexdigest()==backup_hash
    listing=subprocess.run(['docker','--context',CONTEXT,'exec','-i',CLONE,'pg_restore','--list'],input=second.read_bytes(),capture_output=True)
    assert listing.returncode==0
    record('backup-terminal.json',{'backupSHA256':backup_hash,'copySHA256':backup_hash,'bytes':backup.stat().st_size,'privateMode':'0600','archiveListValid':True})
    assert source_fingerprint()==before
    with psycopg.connect(host='127.0.0.1',port=18431,dbname='postgres',user='aos_app',autocommit=True) as admin:
        assert admin.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]=='7695416748450308141'
        assert admin.execute('SELECT 1 FROM pg_database WHERE datname=%s',(DATABASE,)).fetchone() is None
        record('restore-intent.json',{'backupSHA256':backup_hash,'ownedDatabase':DATABASE,'singleTransaction':True,'replicaModeOnlyThisSubprocess':True})
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
    with second.open('rb') as stream:
        restored=subprocess.run(['docker','--context',CONTEXT,'exec','-i','-e','PGOPTIONS=-c session_replication_role=replica',CLONE,
            'pg_restore','--exit-on-error','--single-transaction','-U','aos_app','-d',DATABASE],stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (OUT/'restore.log').write_bytes(restored.stdout+restored.stderr)
    assert restored.returncode==0, 'Restore failed: reconcile owned DB, do not resend'
    after=previous.fingerprint(DATABASE);assert after==before
    source_after=source_fingerprint();assert source_after==before
    record('result.json',{'currentSourceCluster':meta['cluster'],'sourceVersion':'a0v_159','backupSHA256':backup_hash,
        'twoCopiesMatch':True,'ownedRestoreDatabase':DATABASE,'all647TableDataHashesAndCountsMatch':True,
        'sourceBeforeAfterUnchanged':True,'schemaACLAndSequencesFullyCompared':False,
        'continuousZeroExecutionWindowProven':False,'actualDatabaseMigrated':False,'actualServicesRestarted':False,'oldRunReplay':False})
    print(json.dumps({'freshBackupAndCopy':True,'restoredTables':len(after),'allDataMatch':True,'sourceUnchanged':True,'actualMigration':False}))
