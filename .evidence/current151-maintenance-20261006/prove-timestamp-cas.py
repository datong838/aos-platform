"""Synthetic native-PG CAS proof, no connection to the current authoritative DB."""
import importlib.util,json,os,secrets,subprocess,time
from pathlib import Path
root=Path.cwd();s=importlib.util.spec_from_file_location('repair151',root/'scripts/a0v_current_151_maintenance.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
def gate():
 m.read_task(thread=m.THREAD)
 if subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()!=head:raise RuntimeError('HEAD drift')
 if subprocess.check_output(['git','branch','--show-current'],text=True).strip()!='m1':raise RuntimeError('branch drift')
gate();context='colima-aos-a0v-test-only';image='sha256:73ab830fbe32945cf873ebc20ca0aceb532a73a3d4fda1684d1b4b9e0a965fe3';name='current151-source-'+secrets.token_hex(6);volume=name+'-data';state=root.parent/'aos-recovery'/name;state.mkdir(mode=0o700)
def save(name,data):
 with os.fdopen(os.open(state/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
save('intent.json',dict(thread=m.THREAD,task=m.TASK,authority=m.BASE,head=head,container=name,volume=volume,image=image,current_source_touched=False))
def run(args,data=None):
 gate();return subprocess.run(['docker','--context',context]+args,input=data,capture_output=True,timeout=60)
r=run(['run','-d','--name',name,'--network','none','--cpus','1','--memory','768m','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',volume+':/var/lib/postgresql/data',image]);save('create-terminal.json',{'exit_code':r.returncode});assert r.returncode==0
for _ in range(30):
 if run(['exec',name,'pg_isready','-U','aos_app']).returncode==0:break
 time.sleep(1)
else:raise RuntimeError('isolated proof PG not ready')
item=json.loads(run(['inspect',name]).stdout)[0];m.require_isolated151(item,name=name,image=image)
def pg(statement):return run(['exec','-i',name,'psql','-U','aos_app','-d','postgres','-Atq','-v','ON_ERROR_STOP=1','-f','-'],statement.encode())
setup="""CREATE TABLE meta_org(id text primary key,name text,updated_at timestamptz);
CREATE TABLE meta_workspace(org_id text,project_id text,name text,updated_at timestamptz,primary key(org_id,project_id));
CREATE TABLE meta_membership(org_id text,project_id text,subject text,role text,updated_at timestamptz,primary key(org_id,project_id,subject));
INSERT INTO meta_org VALUES('org-org','preserved','2026-10-06T00:00:00+00:00');
INSERT INTO meta_workspace VALUES('org-org','dev-project','preserved','2026-10-06T00:00:00+00:00');
INSERT INTO meta_membership VALUES('org-org','dev-project','existing','viewer','2026-10-06T00:00:00+00:00');"""
assert pg(setup).returncode==0
def rows():
 result={}
 for table in m.TENANT_TIMESTAMP_TABLES151:
  r=pg("BEGIN READ ONLY;SET LOCAL timezone='UTC';SELECT json_agg(row_to_json(t)) FROM public."+table+" t;COMMIT;")
  assert r.returncode==0;result[table]=json.loads(r.stdout)
 return result
import copy
live=rows();original=copy.deepcopy(live)
for row in original.values():row[0]['updated_at']='2026-10-01T00:00:00+00:00'
# Change second table after freezing the CAS, so first UPDATE executes before mismatch.
assert pg("UPDATE meta_workspace SET name='changed-after-CAS-freeze'").returncode==0
drifted=rows()
save('negative-attempt.json',{'head':head});bad=pg(m.build_tenant_timestamp_repair151(original,live).as_string());save('negative-terminal.json',{'exit_code':bad.returncode,'expected_failure':'TENANT_TIMESTAMP_CAS_MISMATCH' in bad.stderr.decode()})
assert bad.returncode!=0 and b'TENANT_TIMESTAMP_CAS_MISMATCH' in bad.stderr and rows()==drifted
assert pg("UPDATE meta_workspace SET name='preserved'").returncode==0
assert rows()==live
save('positive-attempt.json',{'head':head});good=pg(m.build_tenant_timestamp_repair151(original,live).as_string());save('positive-terminal.json',{'exit_code':good.returncode});assert good.returncode==0 and rows()==original
try:m.build_tenant_timestamp_repair151(original,rows())
except m.Maintenance151Blocked:replay_rejected=True
else:raise AssertionError('already-repaired replay accepted')
report=dict(outcome='NATIVE_PG_TIMESTAMP_CAS_PROOF_GREEN',head=head,source_touched=False,negative_atomic_rollback=True,positive_exact_original_rows=True,already_repaired_replay_rejected=replay_rejected,state=str(state),container=name,volume=volume)
save('result.json',report);(root/'.evidence/current151-maintenance-20261006/timestamp-cas-native-proof.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
