"""Continue completed owned restore: clone-only original maintenance contract."""
import importlib.util,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import subprocess,sys
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('r',P/'rehearse.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
s=importlib.util.spec_from_file_location('mc',r.ROOT/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(s);sys.modules[s.name]=mc;s.loader.exec_module(mc)
assert mc.load_authority()['project_revision']=='AOS-001998'
lease=next(x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==r.NAME)
assert lease['owner']==r.OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
consumption=json.loads((P/'consumption-r1.json').read_text());assert consumption['status']=='CONSUMED_MATERIAL_REVIEW' and consumption['execution_authorized'] is False
for name,digest in consumption['baseline']['files'].items():assert hashlib.sha256((r.ROOT/name).read_bytes()).hexdigest()==digest
clone=json.loads(r.docker('inspect',r.NAME,text=True,capture_output=True).stdout)[0]
assert clone['State']['Running'] and clone['HostConfig']['NetworkMode']=='none' and not clone['HostConfig']['PortBindings']
assert len(clone['Mounts'])==1 and clone['Mounts'][0]['Name']==r.NAME
comparison=json.loads((P/'finite-schema-comparison.json').read_text());assert comparison['otherSchemaBytesEqual'] and comparison['clone650TablesEqual']
before=json.loads((P/'source-fixed-key-before.json').read_text())
assert r.fingerprint(r.NAME,r.DB)==before['fingerprints'] and r.fingerprint(r.SOURCE,'aos_meta_head')==before['fingerprints']
for f,d in json.loads((P/'backup-verified.json').read_text())['files'].items():assert hashlib.sha256((P/'private'/f).read_bytes()).hexdigest()==d
query="SELECT row_to_json(x) FROM (SELECT i.database_role::text,i.host_id,i.revision,i.database_role_oid::text AS stored_oid,r.oid::text AS current_oid FROM extension_runtime_host_identity i JOIN pg_roles r ON r.rolname=i.database_role::text WHERE i.database_role='aos_a0v_directory_20260912')x;"
def read(q):return r.sql(r.NAME,r.DB,'BEGIN READ ONLY;'+q+'COMMIT;')
identity=json.loads(read(query));assert identity['revision']==1 and identity['stored_oid']!=identity['current_oid']
key=r.NAME+'-rebind';digest='sha256:'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
command="SELECT extension_runtime_bind_host_identity('aos_a0v_directory_20260912','a0v-local-ecommerce-host-20260912',true,1,'isolated-maintainer','"+key+"','"+digest+"');"
r.record('rebind-intent.json',{'container':clone['Id'],'identity':identity,'idempotencyKey':key,'requestHash':digest,'cloneOnly':True})
assert r.sql(r.NAME,r.DB,command).strip()=='2'
rebound=json.loads(read(query));assert rebound['revision']==2 and rebound['stored_oid']==rebound['current_oid']
after=r.fingerprint(r.NAME,r.DB);changed=sorted(k for k in after if after[k]!=before['fingerprints'][k]);assert changed==['public.extension_runtime_host_command_receipt','public.extension_runtime_host_identity','public.extension_runtime_host_identity_revision']
assert r.sql(r.NAME,r.DB,command).strip()=='2' and r.fingerprint(r.NAME,r.DB)==after
negatives=[]
for label,q,error in [('oldCAS',command.replace(key,key+'-old-cas'),'revision conflict'),('sameKeyDifferentHash',command.replace(digest,'sha256:'+'0'*64),'idempotency conflict')]:
 try:r.sql(r.NAME,r.DB,q)
 except subprocess.CalledProcessError as e:assert error in e.stderr;negatives.append(label)
 else:raise AssertionError('negative passed')
assert r.fingerprint(r.NAME,r.DB)==after
history=json.loads(read("SELECT json_agg(row_to_json(x)) FROM (SELECT revision,database_role_oid::text FROM extension_runtime_host_identity_revision WHERE database_role='aos_a0v_directory_20260912' ORDER BY revision)x;"))
assert history==[{'revision':1,'database_role_oid':identity['stored_oid']},{'revision':2,'database_role_oid':identity['current_oid']}]
assert r.fingerprint(r.SOURCE,'aos_meta_head')==before['fingerprints'] and r.metadata(r.SOURCE,'aos_meta_head')==before['metadata']
r.record('verification.json',{'outcome':'DURABLE_FULL_RESTORE_AND_CLONE_HOST_OID_REBIND_GREEN','source650Unchanged':True,'sourceMetadataUnchanged':True,'complete650RestoreEquality':True,'schemaOnlyExactTwoAssociativeAndRegroupings':True,'otherSchemaBytesEqual':True,'changedCloneTables':changed,'other647TablesUnchanged':True,'historyPreserved':True,'sameRequestNoAppend':True,'negativeGates':negatives,'currentDatabaseWrites':False,'hostActivated':False,'eightWorkbenchesAccepted':False,'retainedCloneVolume':r.NAME,'cloneContainer':clone['Id']})
print('DURABLE_FULL_RESTORE_AND_CLONE_HOST_OID_REBIND_GREEN')
