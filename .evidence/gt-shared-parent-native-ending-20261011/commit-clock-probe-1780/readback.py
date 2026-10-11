"""Independent read-only reconciliation of terminal trials; never invokes probe."""
import hashlib,json,pathlib,subprocess
import psycopg
from psycopg import sql
B=pathlib.Path(__file__).resolve().parent;r=B/'r4';R=B.parents[2];v=json.loads((r/'verification.json').read_text());i=json.loads((r/'installation-terminal.json').read_text());l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());ns=i['schema'];assert ns.startswith('test_owned_clock_') and len(ns)==49
with psycopg.connect(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile']) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster'];states={x['label']:c.execute('SELECT pg_xact_status(%s::xid8)',(x['xid'],)).fetchone()[0] for x in v['cases']};assert states==v['independent_xid_states'];rows=c.execute(sql.SQL('SELECT label,xid::text FROM {}.marker ORDER BY label').format(sql.Identifier(ns))).fetchall();assert [list(x) for x in rows]==v['markers'];meta=c.execute("SELECT p.prosrc,p.probin,p.prosecdef,p.provolatile,p.proparallel,p.proconfig FROM pg_proc p WHERE p.oid=%s::regprocedure",(ns+'.arm(integer)',)).fetchone();assert meta[0]=='aos_test_clock_arm' and not meta[2] and meta[3:5]==('v','u')
 for role in ['aos_runtime','aos_provider_capacity_occupation','aos_physical_capacity_occupation_owner']:
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,ns+'.arm(integer)')).fetchone()[0]
 pg_read_clock=c.execute('SELECT clock_timestamp()::text').fetchone()[0]
raw=subprocess.check_output(['docker','--context','desktop-linux','exec',l['name'],'cat',meta[1]],timeout=30);assert hashlib.sha256(raw).hexdigest()==i['binary_sha256']==hashlib.sha256((r/'probe.so').read_bytes()).hexdigest()
clock=v['clock_order'];assert clock['check']<clock['deadline']<clock['after_delay']<=clock['postcommit_callback'];assert states['after_check_delay']=='committed';assert states['expired']=='aborted'
out={'status':'READONLY_COUNTEREXAMPLE_RECONCILED','schema':ns,'xid_states':states,'markers':rows,'binary_exact':True,'acl_runtime_closed':True,'database_readback_clock':pg_read_clock,'gap_after_deadline_microseconds':clock['after_delay']-clock['deadline'],'direct_durable_flush_timestamp':False,'no_probe_invocation':True,'no_root_or_execution_authority':True}
with (B/'independent-readback.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps({'status':out['status'],'gap_microseconds':out['gap_after_deadline_microseconds']}))
