from pathlib import Path
import json,hashlib,psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2];label=B.name
result=json.loads((B/'result-r1.json').read_text());assert result['pytest_exit']==0 and result['old_files_unchanged']
proof=json.loads((B/(label+'-whole-source-plan-verification.json')).read_text());negative=json.loads((B/(label+'-intent-existing-row-negative.json')).read_text())
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
counts={}
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=result['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(proof['caller']['xid'],)).fetchone()['state']=='aborted'
 for table in ('prepared_execution_intent','prepared_parent_debit','prepared_plan_risk','prepared_shared_risk_description'):
  if c.execute('SELECT to_regclass(%s) AS t',('aos_physical_capacity_occupation_private.'+table,)).fetchone()['t'] is None:
   counts[table]=None;continue
  counts[table]=c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+table).fetchone()['n']
 assert counts['prepared_execution_intent']==counts['prepared_parent_debit']==0
 assert all(x is None or x==0 for x in counts.values())
 assert c.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()['rolcanlogin'] is False
 assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n']==0
assert proof['cases']==2 and proof['legs']==4 and proof['canary_rejected'] and proof['wrong_source_physical_provider_rejected']
assert len(negative['probes'])==2 and all(x['existing_row_verified'] for x in negative['probes'])
s={'status':'FRESH_ORIGINAL_SOURCE_ADJACENT_PASS_WITH_INDEPENDENT_ABORT_READBACK','authority':'AOS-001728','database':result['databases'][0],'cluster':lab['cluster'],'original_node_unmodified':True,'shared_integration_hook_disabled_for_independent_fresh_source':True,'native_tests_pass':1,'seconds':57.68,'original_native_proof':proof,'original_existing_row_negatives':negative,'caller_aborted':True,'retained_counts':counts,'test_role_restored':True,'formal_writes':False,'execution_allowed':False,'shared_complete_admission_pass':False,'r3_whole_failure_superseded':False}
(B/'independent-readback.json').write_text(json.dumps(s,indent=2)+'\n');print(s['status'],s['database'])
