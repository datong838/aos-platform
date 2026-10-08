"""Independent read-only rollback, ACL, original Source and preservation audit."""
import json,subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((B/'lab.json').read_text());db=json.loads((B/'native-r3-result.json').read_text())['database']
before=json.loads((B/'preflight.json').read_text())['old_containers']
after=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect']+[x['Id'] for x in before],text=True))
assert len(before)==len(after)
for a,b in zip(after,before):
 for key,value in {'Id':a['Id'],'name':a['Name'],'started':a['State']['StartedAt'],'mounts':a['Mounts'],'ports':a['HostConfig']['PortBindings']}.items():assert b[key]==value
with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 assert c.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==lab['cluster']
 assert c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
 role=c.execute("SELECT rolcanlogin AS login,(SELECT count(*) FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid) AS memberships FROM pg_roles r WHERE rolname='aos_provider_capacity_occupation'").fetchone();assert role==dict(login=False,memberships=0)
 tables={x:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+x).fetchone()['n'] for x in ('account_guard','prepared_parent_debit','prepared_execution_intent')}
 assert tables==dict(account_guard=1,prepared_parent_debit=0,prepared_execution_intent=0)
 race=json.loads((R/'.evidence/gt-atomic-model-admission-20261008/source-newjudge-joint-r3-guard-race.json').read_text())
 assert c.execute('SELECT version FROM aos_physical_capacity_occupation_private.account_guard').fetchone()['version']==race['writer']['version']
 source_count=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source_count==1
 proof=json.loads((R/'.evidence/gt-atomic-model-admission-20261008/source-newjudge-native-positive-1606.json').read_text());xid=proof['original_fact']['xid'];status=c.execute('SELECT pg_xact_status(%s::xid8) AS status',(xid,)).fetchone()['status'];assert status=='aborted'
 assert c.execute("SELECT to_regprocedure('public.prepare_capacity_judge_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,text)') AS fn").fetchone()['fn'] is None
result=dict(database=db,cluster=lab['cluster'],migration='a0v_159',source_count=source_count,occupation_role=role,private_prepared_rows=tables,account_guard_reason='original actual guard-race writer COMMIT retained; newJudge caller aborted',newjudge_transaction=xid,transaction_status=status,trial_function_removed=True,old_containers_unchanged=True,business_firstchain=False)
(B/'native-r3-independent.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
