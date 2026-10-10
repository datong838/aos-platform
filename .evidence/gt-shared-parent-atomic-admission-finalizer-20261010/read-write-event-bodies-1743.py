"""Read exact native event bodies from the reconciled isolated database."""
import json,hashlib
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-atomic-admission-finalizer-20261010';N=B/'write-closure-native-1743-r1'
v=json.loads((B/'write-closure-verification-1743.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
capture=[json.loads(x) for x in (N/'native-write-capture.jsonl').read_text().splitlines()][-1]
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=v['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(v['caller']['xid'],)).fetchone()['state']=='aborted'
 ids={r['relid'] for r in capture['write_counters']}
 closure=ids|{r['conrelid'] for r in capture['constraints'] if r['confrelid'] in ids}
 relations=c.execute('SELECT c.oid,n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=ANY(%s) ORDER BY n.nspname,c.relname',(list(closure),)).fetchall()
 bodies=c.execute('SELECT DISTINCT p.oid::regprocedure::text AS signature,pg_get_userbyid(p.proowner) AS owner,p.prosecdef,p.proconfig,l.lanname,p.prosrc FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_language l ON l.oid=p.prolang WHERE t.tgrelid=ANY(%s) ORDER BY signature',(list(closure),)).fetchall()
 for r in bodies:r['body_sha256']=hashlib.sha256(r['prosrc'].encode()).hexdigest()
 for r in capture['triggers']:
  matches=[p for p in bodies if p['signature']==r['function']];assert len(matches)==1 and matches[0]['body_sha256']==r['body_hash']
 output=dict(status='NATIVE_WRITE_EVENT_BODIES_FROZEN_READ_ONLY',authority='AOS-001743',database=v['database'],cluster=lab['cluster'],caller_aborted=True,write_relations=len(ids),incoming_constraint_relations=len(closure-ids),relations=relations,trigger_functions=bodies,capture_proves_pending_event_queue=False,transitive_closure_proven=False,execution_allowed=False)
 (B/'write-event-bodies-1743.json').open('x').write(json.dumps(output,indent=2)+'\n')
 print(json.dumps(dict(status=output['status'],relations=len(relations),functions=len(bodies),languages=sorted({x['lanname'] for x in bodies}),incoming_relations=[x['nspname']+'.'+x['relname'] for x in relations if x['oid'] not in ids])))
