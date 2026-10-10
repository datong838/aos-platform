"""Test-only native queue reader; retained schema; reconcile unknown effects."""
import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());db='aos_test_05f1a1dcd51f_ti4_test'
image=(B/'image-id.txt').read_text().strip();suffix=uuid.uuid4().hex;schema='test_owned_pending_'+suffix;artifact='aos-pending-artifact-'+suffix;library='/tmp/aos_pending_'+suffix+'.so'
def call(args):return subprocess.check_output(['docker',*args],text=True).strip()
state=json.loads(call(['inspect',lab['name']]))[0];assert state['Id']==lab['container_id'] and state['Image']==lab['image'] and state['State']['Running']
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row)
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT to_regprocedure(%s) AS proc',(schema+'.pending(oid)',)).fetchone()['proc'] is None
attempt=dict(schema=schema,library=library,artifact_container=artifact,image=image,cluster=lab['cluster'],database=db,red_missing_native_function=True,original_tables_written=False)
(B/'attempt.json').open('x').write(json.dumps(attempt,indent=2)+'\n')
id=call(['create','--network','none','--name',artifact,image]);(B/'artifact-container.json').open('x').write(json.dumps(dict(id=id)))
subprocess.run(['docker','cp',artifact+':/aos_pending_probe_1744.so',str(B/'probe.so')],check=True)
sha=hashlib.sha256((B/'probe.so').read_bytes()).hexdigest();subprocess.run(['docker','cp',str(B/'probe.so'),lab['name']+':'+library],check=True)
assert call(['exec',lab['name'],'sha256sum',library]).split()[0]==sha
with psycopg.connect(**params) as c:
 c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION aos_app')
 c.execute(sql.SQL('CREATE FUNCTION '+schema+".pending(oid) RETURNS boolean AS {},'aos_test_pending_on_relation' LANGUAGE c STRICT STABLE SET search_path=pg_catalog").format(sql.Literal(library)))
 c.execute('REVOKE ALL ON FUNCTION '+schema+'.pending(oid) FROM PUBLIC')
 c.execute('CREATE TABLE '+schema+'.q(id integer PRIMARY KEY)')
 c.execute('CREATE TABLE '+schema+'.audit(id integer,phase text,pending boolean)')
 for name in ('probe','later'):
  c.execute('CREATE FUNCTION '+schema+'.'+name+"() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN INSERT INTO "+schema+".audit VALUES(NEW.id,'"+name+"',"+schema+".pending('"+schema+".q'::regclass)); RETURN NEW; END $$")
  c.execute('REVOKE ALL ON FUNCTION '+schema+'.'+name+'() FROM PUBLIC')
 for trigger,fn in [('a_probe','probe'),('z_later','later')]:c.execute('CREATE CONSTRAINT TRIGGER '+trigger+' AFTER INSERT ON '+schema+'.q DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+schema+'.'+fn+'()')
 for role in ('aos_runtime','aos_provider_capacity_occupation'):
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,schema+'.pending(oid)')).fetchone()['allowed']
 c.commit()
 (B/'installation.json').open('x').write(json.dumps(dict(schema=schema,library=library,binary_sha256=sha,committed=True,public_runtime_execute=False),indent=2)+'\n')
 def pending():return c.execute('SELECT '+schema+'.pending(%s::regclass) AS p',(schema+'.q',)).fetchone()['p']
 assert pending() is False
 xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
 c.execute('INSERT INTO '+schema+'.q VALUES(1)');assert pending() is True
 c.execute('SAVEPOINT drain')
 c.execute('SET CONSTRAINTS '+schema+'.a_probe,'+schema+'.z_later IMMEDIATE')
 samples=c.execute('SELECT * FROM '+schema+'.audit ORDER BY phase').fetchall();assert samples==[dict(id=1,phase='later',pending=True),dict(id=1,phase='probe',pending=True)]
 assert pending() is False
 c.execute('ROLLBACK TO SAVEPOINT drain');assert pending() is True
 assert c.execute('SELECT count(*) AS n FROM '+schema+'.audit').fetchone()['n']==0
 c.rollback()
 # Actual COMMIT independently tests the reader inside its currently executing event.
 c.execute('INSERT INTO '+schema+'.q VALUES(2)');commit_xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
 (B/'commit-intent.json').open('x').write(json.dumps(dict(xid=commit_xid,schema=schema)))
 c.commit()
 (B/'commit-terminal.json').open('x').write(json.dumps(dict(xid=commit_xid,returned=True)))
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 states=[c.execute('SELECT pg_xact_status(%s::xid8) AS s',(x,)).fetchone()['s'] for x in (xid,commit_xid)];assert states==['aborted','committed']
 assert c.execute('SELECT id FROM '+schema+'.q').fetchall()==[dict(id=2)]
 samples=c.execute('SELECT * FROM '+schema+'.audit ORDER BY phase').fetchall();assert samples==[dict(id=2,phase='later',pending=True),dict(id=2,phase='probe',pending=True)]
 meta=c.execute('SELECT prosrc,probin,prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(schema+'.pending(oid)',)).fetchone();assert meta==dict(prosrc='aos_test_pending_on_relation',probin=library,prosecdef=False,proconfig=['search_path=pg_catalog'])
 flags=c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone();assert not any(flags.values())
 assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
out=dict(status='NATIVE_PENDING_READER_CURRENT_EVENT_COUNTEREXAMPLE_VERIFIED',authority='AOS-001744',schema=schema,database=db,cluster=lab['cluster'],binary_sha256=sha,red_missing_function=True,baseline_pending=False,after_insert_pending=True,inside_executing_trigger_pending=True,after_exact_scoped_drain_pending=False,savepoint_rollback_restores_pending=True,xids=[xid,commit_xid],independent_states=states,actual_commit_samples=samples,role_unchanged=True,original_business_tables_written=False,pending_queue_enumerated=False,full_admission=False,execution_allowed=False)
(B/'verification.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(status=out['status'],states=states,current_event_pending=True,rollback_restores_pending=True)))
