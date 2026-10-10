"""Single owned isolated two-callback trial. Never rerun after unknown effects."""
import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2]
l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
u=uuid.uuid4().hex;ns='test_owned_order_'+u;lib='/tmp/aos_order_'+u+'.so';artifact='aos-order-artifact-'+u
params=dict(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile'])
def docker(args):return subprocess.check_output(['docker',*args],text=True).strip()
st=json.loads(docker(['inspect',l['name']]))[0]
assert st['Id']==l['container_id'] and st['Image']==l['image'] and st['State']['Running']
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster']
 roles=c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_provider_capacity_occupation','aos_physical_capacity_occupation_owner') ORDER BY rolname").fetchall();assert len(roles)==2 and all(not any(r[1:]) for r in roles)
image=(B/'image-id.txt').read_text().strip();source_sha=hashlib.sha256((B/'probe.c').read_bytes()).hexdigest()
(B/'attempt.json').open('x').write(json.dumps(dict(schema=ns,library=lib,image=image,source_sha256=source_sha,container_id=l['container_id'],database=params['dbname'],cluster=l['cluster'],full_admission=False),indent=2)+'\n')
aid=docker(['create','--network','none','--name',artifact,image]);(B/'artifact.json').open('x').write(json.dumps(dict(id=aid)))
subprocess.run(['docker','cp',artifact+':/aos_order_probe.so',str(B/'probe.so')],check=True)
sha=hashlib.sha256((B/'probe.so').read_bytes()).hexdigest();subprocess.run(['docker','cp',str(B/'probe.so'),l['name']+':'+lib],check=True)
assert docker(['exec',l['name'],'sha256sum',lib]).split()[0]==sha
body=" BEGIN RAISE EXCEPTION 'TEST_ORDER_DEFERRED_REJECT' USING ERRCODE='23514'; END "
with psycopg.connect(**params) as c:
 c.execute('CREATE SCHEMA '+ns+' AUTHORIZATION aos_app')
 c.execute(sql.SQL('CREATE FUNCTION '+ns+".arm(oid,oid,boolean) RETURNS void AS {},'aos_test_order_arm' LANGUAGE c STRICT VOLATILE PARALLEL UNSAFE SET search_path=pg_catalog").format(sql.Literal(lib)))
 c.execute('REVOKE ALL ON FUNCTION '+ns+'.arm(oid,oid,boolean) FROM PUBLIC')
 c.execute('CREATE FUNCTION '+ns+'.reject() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS '+sql.Literal(body).as_string(c))
 c.execute('REVOKE ALL ON FUNCTION '+ns+'.reject() FROM PUBLIC')
 for label in ['ordinary','observer_first','observer_last']:
  c.execute('CREATE TABLE '+ns+'.'+label+'(id integer PRIMARY KEY)')
  c.execute('CREATE CONSTRAINT TRIGGER reject_event AFTER INSERT ON '+ns+'.'+label+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+ns+'.reject()')
  c.execute('CREATE TABLE '+ns+'.'+label+'_observation(id integer PRIMARY KEY,pending boolean NOT NULL)')
 c.execute('CREATE TABLE '+ns+'.marker(label text PRIMARY KEY,xid xid8 NOT NULL)')
 for role in ['aos_runtime','aos_provider_capacity_occupation']:
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,ns+'.arm(oid,oid,boolean)')).fetchone()[0]
 c.commit()
(B/'installation.json').open('x').write(json.dumps(dict(schema=ns,library=lib,binary_sha256=sha,committed=True,public_runtime_closed=True),indent=2)+'\n')
cases=[]
for label,first in [('ordinary',None),('observer_first',True),('observer_last',False)]:
 with psycopg.connect(**params) as c:
  xid=c.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
  c.execute('INSERT INTO '+ns+'.marker VALUES(%s,%s::xid8)',(label,xid))
  if first is None:c.execute('INSERT INTO '+ns+'.ordinary VALUES(1)')
  else:c.execute('SELECT '+ns+'.arm(%s::regclass,%s::regclass,%s)',(ns+'.'+label,ns+'.'+label+'_observation',first))
  (B/(label+'-intent.json')).open('x').write(json.dumps(dict(xid=xid,registration_writer_then_observer=first)))
  try:c.commit();outcome='committed';error=None
  except psycopg.Error as e:outcome='rejected';error=str(e).splitlines()[0];c.rollback()
  assert c.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
  row=dict(label=label,xid=xid,outcome=outcome,error=error);cases.append(row)
  (B/(label+'-terminal.json')).open('x').write(json.dumps(row,indent=2)+'\n')
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 states={r['label']:c.execute('SELECT pg_xact_status(%s::xid8)',(r['xid'],)).fetchone()[0] for r in cases}
 assert states==dict(ordinary='aborted',observer_first='committed',observer_last='aborted'),states
 counts={t:c.execute('SELECT count(*) FROM '+ns+'.'+t).fetchone()[0] for t in ['ordinary','observer_first','observer_last','ordinary_observation','observer_first_observation','observer_last_observation','marker']}
 assert counts==dict(ordinary=0,observer_first=1,observer_last=0,ordinary_observation=0,observer_first_observation=1,observer_last_observation=0,marker=1),counts
 observed=c.execute('SELECT id,pending FROM '+ns+'.observer_first_observation').fetchall();assert observed==[(1,False)]
 assert cases[0]['error']=='TEST_ORDER_DEFERRED_REJECT' and cases[2]['error']=='TEST_ORDER_OBSERVER_PENDING_REJECTED'
 assert c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',(ns+'.reject()',)).fetchone()[0]==body
 triggers=c.execute('SELECT tgenabled,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid IN (%s::regclass,%s::regclass,%s::regclass) AND NOT tgisinternal',(ns+'.ordinary',ns+'.observer_first',ns+'.observer_last')).fetchall();assert triggers==[('O',True,True)]*3
 roles_after=c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_provider_capacity_occupation','aos_physical_capacity_occupation_owner') ORDER BY rolname").fetchall();assert roles_after==roles
 assert c.execute("SELECT count(*) FROM pg_auth_members WHERE member IN ('aos_provider_capacity_occupation'::regrole,'aos_physical_capacity_occupation_owner'::regrole) OR roleid IN ('aos_provider_capacity_occupation'::regrole,'aos_physical_capacity_occupation_owner'::regrole)").fetchone()[0]==0
 verifier=docker(['exec',l['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so']).split()[0];assert verifier=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
st2=json.loads(docker(['inspect',l['name']]))[0];assert st2['State']['StartedAt']==st['State']['StartedAt'] and st2['RestartCount']==st['RestartCount']
result=dict(status='TWO_CALLBACK_ACTUAL_COMMIT_ORDER_COUNTEREXAMPLE_VERIFIED',authority='AOS-001747',schema=ns,cases=cases,independent_xid_states=states,counts=counts,observer_first_record=observed,guard_body_and_enabled_triggers_exact=True,roles_and_memberships_unchanged=True,original_verifier_sha256=verifier,lab_not_restarted=True,source_sha256=source_sha,binary_sha256=sha,full_admission=False,execution_allowed=False,full_task_delivered=False)
(B/'verification.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],states=states,counts=counts)))
