"""Approved exact Host identity maintenance; native CAS only, no activation."""
import importlib.util,sys,json,hashlib,os,shutil
from pathlib import Path
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
OUT=P/'current-host-oid-maintenance-20261013'
ROOT=P.parents[1]
s=importlib.util.spec_from_file_location('restore',ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(s);sys.modules[s.name]=mc;s.loader.exec_module(mc)
TASK='qyh-full-system-restoration-20261011'
REVIEW=ROOT/'.evidence/qyh-current-host-oid-maintenance-review-20261013'
QUERY="SELECT row_to_json(x) FROM (SELECT i.database_role::text,i.host_id,i.revision,i.database_role_oid::text AS stored_oid,r.oid::text AS current_oid FROM extension_runtime_host_identity i JOIN pg_roles r ON r.rolname=i.database_role::text WHERE i.database_role='aos_a0v_directory_20260912')x;"
def record(n,v):
 with (OUT/n).open('x') as f:json.dump(v,f,indent=2)
def read(q):return r.sql(r.SOURCE,'aos_meta_head','BEGIN READ ONLY;'+q+'COMMIT;')
def guards():
 assert mc.load_authority()['project_revision']=='AOS-001999'
 l=next(x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==TASK)
 assert l['owner']==r.OWNER and datetime.fromisoformat(l['lease_expires_at'])>datetime.now(timezone.utc)
 assert 'aos-platform/maintenance/qiyuehui-restored-data-volume' in l['scope']
 source=json.loads(r.docker('inspect',r.SOURCE,text=True,capture_output=True).stdout)[0]
 assert source['Id']==r.CID and source['State']['Running'] and source['Image']==r.IMAGE
 assert len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
 native=json.loads(read("SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'schema',(SELECT version_num FROM alembic_version),'enabled',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherSessions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),'owner',(SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE proname='extension_runtime_bind_host_identity'),'currentUser',current_user);"))
 assert native=={'cluster':'7695302940039200809','schema':'a0v_161','enabled':0,'otherSessions':0,'owner':'aos_app','currentUser':'aos_app'}
 identity=json.loads(read(QUERY));assert identity['database_role']=='aos_a0v_directory_20260912' and identity['host_id']=='a0v-local-ecommerce-host-20260912'
 return source,native,identity

def prepare():
 OUT.mkdir();source,native,identity=guards()
 assert identity['revision']==1 and identity['stored_oid']=='203325' and identity['current_oid']=='16385'
 restored=ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013'
 v=json.loads((restored/'verification.json').read_text());assert v['outcome']=='DURABLE_FULL_RESTORE_AND_CLONE_HOST_OID_REBIND_GREEN'
 before=r.fingerprint(r.SOURCE,'aos_meta_head');meta=r.metadata(r.SOURCE,'aos_meta_head')
 baseline=json.loads((restored/'source-fixed-key-before.json').read_text());assert before==baseline['fingerprints'] and meta==baseline['metadata']
 record('prepare-intent.json',{'task':TASK,'authority':'AOS-001999','source':r.CID,'sourceVolume':source['Mounts'][0]['Name'],'native':native,'identity':identity,'writes':False})
 private=OUT/'private';private.mkdir(mode=0o700);hashes={}
 for filename,args in [('current.dump',('pg_dump','-U','aos_app','-d','aos_meta_head','-Fc')),('globals.sql',('pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'))]:
  p=private/filename
  with os.fdopen(os.open(p,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'wb') as f:r.docker('exec',r.SOURCE,*args,stdout=f,stderr=r.subprocess.PIPE)
  c=private/(filename+'.second');shutil.copyfile(p,c);c.chmod(0o600)
  for x in (p,c):hashes[x.name]=hashlib.sha256(x.read_bytes()).hexdigest()
  assert hashes[p.name]==hashes[c.name]
 for args in [('--list',),('--file=/dev/null',)]:r.docker('exec','-i',r.SOURCE,'pg_restore',*args,input=(private/'current.dump').read_bytes(),stdout=r.subprocess.PIPE,stderr=r.subprocess.PIPE)
 assert r.fingerprint(r.SOURCE,'aos_meta_head')==before and r.metadata(r.SOURCE,'aos_meta_head')==meta
 key='qyh-current-host-oid-maintenance-20261013'
 digest='sha256:'+hashlib.sha256(json.dumps({'identity':identity,'files':hashes},sort_keys=True).encode()).hexdigest()
 record('prepared.json',{'identity':identity,'files':hashes,'before':before,'metadata':meta,'idempotencyKey':key,'requestHash':digest,'priorIndependentFullRestoreVerified':True,'newBackupFullyDecoded':True,'sourceWrites':False})
 print('CURRENT_HOST_MAINTENANCE_BACKUP_PREPARED_NO_WRITES')

def execute():
 source,native,identity=guards();prepared=json.loads((OUT/'prepared.json').read_text());assert identity==prepared['identity']
 consumption=json.loads((REVIEW/'consumption-r1.json').read_text());assert consumption['status']=='CONSUMED_MATERIAL_REVIEW' and consumption['execution_authorized'] is False
 for path,digest in consumption['baseline']['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
 assert (REVIEW/'material-1.txt').read_text()==Path(__file__).read_text()
 assert json.loads((REVIEW/'material-2.txt').read_text())['preparedFileSHA256']==hashlib.sha256((OUT/'prepared.json').read_bytes()).hexdigest()
 for name,digest in prepared['files'].items():assert hashlib.sha256((OUT/'private'/name).read_bytes()).hexdigest()==digest
 assert r.fingerprint(r.SOURCE,'aos_meta_head')==prepared['before'] and r.metadata(r.SOURCE,'aos_meta_head')==prepared['metadata']
 key=prepared['idempotencyKey'];digest=prepared['requestHash']
 command="SELECT extension_runtime_bind_host_identity('aos_a0v_directory_20260912','a0v-local-ecommerce-host-20260912',true,1,'codex-authorized-qyh-restoration','"+key+"','"+digest+"');"
 record('execute-intent.json',{'container':r.CID,'commandFunction':'extension_runtime_bind_host_identity','expectedRevision':1,'idempotencyKey':key,'requestHash':digest,'hostActivation':False})
 # Native original function owns transaction/CAS and append-only history.
 assert r.sql(r.SOURCE,'aos_meta_head',command).strip()=='2'
 rebound=json.loads(read(QUERY));assert rebound['revision']==2 and rebound['stored_oid']==rebound['current_oid']=='16385'
 after=r.fingerprint(r.SOURCE,'aos_meta_head');changed=sorted(k for k in after if after[k]!=prepared['before'][k])
 assert changed==['public.extension_runtime_host_command_receipt','public.extension_runtime_host_identity','public.extension_runtime_host_identity_revision']
 assert r.metadata(r.SOURCE,'aos_meta_head')==prepared['metadata']
 history=json.loads(read("SELECT json_agg(row_to_json(x)) FROM (SELECT revision,database_role_oid::text FROM extension_runtime_host_identity_revision WHERE database_role='aos_a0v_directory_20260912' ORDER BY revision)x;"))
 assert history==[{'revision':1,'database_role_oid':'203325'},{'revision':2,'database_role_oid':'16385'}]
 assert json.loads(read("SELECT json_build_object('enabled',(SELECT count(*) FROM extension_runtime_binding WHERE enabled));"))=={'enabled':0}
 newsource=json.loads(r.docker('inspect',r.SOURCE,text=True,capture_output=True).stdout)[0];assert newsource['State']['StartedAt']==source['State']['StartedAt']
 record('verification.json',{'outcome':'CURRENT_HOST_OID_NATIVE_CAS_MAINTENANCE_GREEN','identityBefore':identity,'identityAfter':rebound,'changedTables':changed,'other647TablesUnchanged':True,'schemaRolesSequencesUnchanged':True,'originalHistoryPreserved':True,'sourceVolumeUnchanged':True,'databaseRestarted':False,'enabledBindings':0,'hostActivated':False,'eightWorkbenchesAccepted':False,'afterFingerprints':after})
 print('CURRENT_HOST_OID_NATIVE_CAS_MAINTENANCE_GREEN')

if __name__=='__main__':
 assert len(sys.argv)==2
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='execute':execute()
 else:raise ValueError('explicit prepare/execute only; no automatic retries')
