"""Retained isolated callback-created event controls, no effect replay."""
import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());db='aos_test_05f1a1dcd51f_ti4_test';uid=uuid.uuid4().hex
schema='test_owned_callback_'+uid;artifact='aos-callback-artifact-'+uid;library='/tmp/aos_postdrain_'+uid+'.so';image=(B/'image-id.txt').read_text().strip()
def call(args):return subprocess.check_output(['docker',*args],text=True).strip()
state=json.loads(call(['inspect',lab['name']]))[0];assert state['Id']==lab['container_id'] and state['Image']==lab['image'] and state['State']['Running']
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row)
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
(B/'attempt.json').open('x').write(json.dumps(dict(schema=schema,library=library,artifact_container=artifact,image=image,cluster=lab['cluster'],database=db,original_tables_written=False),indent=2)+'\n')
artifact_id=call(['create','--network','none','--name',artifact,image]);(B/'artifact-container.json').open('x').write(json.dumps(dict(id=artifact_id)))
subprocess.run(['docker','cp',artifact+':/aos_postdrain_probe_1745.so',str(B/'probe.so')],check=True);sha=hashlib.sha256((B/'probe.so').read_bytes()).hexdigest()
subprocess.run(['docker','cp',str(B/'probe.so'),lab['name']+':'+library],check=True);assert call(['exec',lab['name'],'sha256sum',library]).split()[0]==sha
cases=[]
with psycopg.connect(**params) as c:
 c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION aos_app')
 c.execute(sql.SQL('CREATE FUNCTION '+schema+".arm(oid,boolean) RETURNS void AS {},'aos_test_postdrain_arm' LANGUAGE c STRICT VOLATILE SET search_path=pg_catalog").format(sql.Literal(library)))
 c.execute('REVOKE ALL ON FUNCTION '+schema+'.arm(oid,boolean) FROM PUBLIC')
 guardbody=" BEGIN RAISE EXCEPTION 'TEST_OWNED_DEFERRED_REJECT' USING ERRCODE='23514'; END "
 c.execute('CREATE FUNCTION '+schema+'.reject() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS '+sql.Literal(guardbody).as_string(c))
 c.execute('REVOKE ALL ON FUNCTION '+schema+'.reject() FROM PUBLIC')
 for table in ('ordinary','naive','checked'):
  c.execute('CREATE TABLE '+schema+'.'+table+'(id integer PRIMARY KEY)')
  c.execute('CREATE CONSTRAINT TRIGGER reject_event AFTER INSERT ON '+schema+'.'+table+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+schema+'.reject()')
 c.execute('CREATE TABLE '+schema+'.marker(label text PRIMARY KEY,xid xid8 NOT NULL)')
 for role in ('aos_runtime','aos_provider_capacity_occupation'):
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,schema+'.arm(oid,boolean)')).fetchone()['allowed']
 c.commit();(B/'installation.json').open('x').write(json.dumps(dict(schema=schema,library=library,binary_sha256=sha,committed=True,public_runtime_execute=False),indent=2)+'\n')
 for label,reject in [('ordinary',None),('naive',False),('checked',True)]:
  xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
  c.execute('INSERT INTO '+schema+'.marker VALUES(%s,%s::xid8)',(label,xid))
  if reject is None:c.execute('INSERT INTO '+schema+'.ordinary VALUES(1)')
  else:c.execute('SELECT '+schema+'.arm(%s::regclass,%s)',(schema+'.'+label,reject))
  (B/(label+'-commit-intent.json')).open('x').write(json.dumps(dict(xid=xid,label=label)))
  try:
   c.commit();outcome='committed';error=None
  except psycopg.Error as e:
   outcome='rejected';error=str(e).splitlines()[0];c.rollback()
  assert c.info.transaction_status==psycopg.pq.TransactionStatus.IDLE
  row=dict(label=label,xid=xid,outcome=outcome,error=error);cases.append(row)
  (B/(label+'-commit-terminal.json')).open('x').write(json.dumps(row,indent=2)+'\n')
(B/'cases.json').open('x').write(json.dumps(cases,indent=2)+'\n')
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 statuses={r['label']:c.execute('SELECT pg_xact_status(%s::xid8) AS state',(r['xid'],)).fetchone()['state'] for r in cases}
 counts={t:c.execute('SELECT count(*) AS n FROM '+schema+'.'+t).fetchone()['n'] for t in ('ordinary','naive','checked','marker')}
 assert statuses==dict(ordinary='aborted',naive='committed',checked='aborted'),statuses
 assert counts==dict(ordinary=0,naive=1,checked=0,marker=1),counts
 assert cases[0]['error']=='TEST_OWNED_DEFERRED_REJECT' and cases[2]['error']=='TEST_CALLBACK_NEW_PENDING_EVENT_REJECTED'
 native_guard=c.execute('SELECT prosrc,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(schema+'.reject()',)).fetchone();assert native_guard==dict(prosrc=guardbody,proconfig=['search_path=pg_catalog'])
 triggers=c.execute('SELECT tgname,tgdeferrable,tginitdeferred,tgenabled FROM pg_trigger WHERE tgrelid IN (%s::regclass,%s::regclass,%s::regclass) AND NOT tgisinternal',(schema+'.ordinary',schema+'.naive',schema+'.checked')).fetchall();assert len(triggers)==3 and all(t==dict(tgname='reject_event',tgdeferrable=True,tginitdeferred=True,tgenabled='O') for t in triggers)
 meta=c.execute('SELECT prosrc,probin,prosecdef,proconfig,provolatile FROM pg_proc WHERE oid=%s::regprocedure',(schema+'.arm(oid,boolean)',)).fetchone();assert meta==dict(prosrc='aos_test_postdrain_arm',probin=library,prosecdef=False,proconfig=['search_path=pg_catalog'],provolatile='v')
 flags=c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone();assert not any(flags.values())
 assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
state2=json.loads(call(['inspect',lab['name']]))[0];assert state2['State']['StartedAt']==state['State']['StartedAt'] and state2['RestartCount']==state['RestartCount']
result=dict(status='NATIVE_POSTDRAIN_CALLBACK_NEW_EVENT_COUNTEREXAMPLE_VERIFIED',authority='AOS-001745',schema=schema,database=db,cluster=lab['cluster'],binary_sha256=sha,cases=cases,independent_statuses=statuses,owned_counts=counts,ordinary_guard_really_rejects=True,naive_callback_commit_skips_new_deferred_rejection=True,explicit_pending_rejection_control_aborts=True,trigger_bodies_enabled_unchanged=True,role_unchanged=True,container_not_restarted=True,original_business_tables_written=False,full_admission=False,execution_allowed=False)
(B/'verification.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],statuses=statuses,counts=counts)))
