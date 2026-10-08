"""Independent read-only reconciliation after known native RED."""
import json,subprocess,re
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((B/'lab.json').read_text());run=json.loads((B/'native-r2-result.json').read_text());proof=json.loads((B/'four-leg-red.json').read_text())
assert run['pytest_exit']==1 and proof['sqlstate']=='23514' and proof['error'].startswith('CAPACITY_PHYSICAL_CAPACITY_EXCEEDED')
assert len(proof['successful_legs'])==2 and proof['planned_legs']==4 and proof['failed_leg']==dict(case_id='content-subject-1',purpose='target')
assert proof['successful_legs'][0]['debit']['physicalRequests']==1 and proof['successful_legs'][0]['debit']['physicalTokens']==10000
assert proof['source_max_concurrency']==2 and proof['source_limit']['maxTokens']==20000
assert all(x['debit']['allocatedMinor']==1 and x['debit']['parentCapMinor']==10 for x in proof['successful_legs'])
before=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers']
after=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',*[x['Id'] for x in before]],text=True));assert len(before)==len(after)
for a,b in zip(after,before):
 for k,v in dict(Id=a['Id'],name=a['Name'],started=a['State']['StartedAt'],mounts=a['Mounts'],ports=a['HostConfig']['PortBindings']).items():assert b[k]==v
with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=run['database'],passfile=lab['passfile']) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='a0v_159'
 status=c.execute('SELECT pg_xact_status(%s::xid8)',(proof['xid'],)).fetchone()[0];assert status=='aborted'
 counts={t:c.execute('SELECT count(*) FROM aos_physical_capacity_occupation_private.'+t).fetchone()[0] for t in ('account_guard','parent_debit_guard','prepared_parent_debit','prepared_execution_intent')};assert all(v==0 for v in counts.values())
 role=c.execute("SELECT rolcanlogin,(SELECT count(*) FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid) FROM pg_roles r WHERE rolname='aos_provider_capacity_occupation'").fetchone();assert role==(False,0)
 source=c.execute('SELECT count(*) FROM aos_capacity_publication_private.source_publication').fetchone()[0];assert source==1
 assert c.execute("SELECT to_regprocedure('public.prepare_capacity_judge_parent_debit(bytea,jsonb,uuid,text,text,uuid,bigint,text)')").fetchone()[0] is None
(B/'independent-red.json').write_text(json.dumps(dict(database=run['database'],cluster=lab['cluster'],xid=proof['xid'],status=status,prepared_counts=counts,retained_source=source,occupation_role=role,old_resources_unchanged=True,complete_four_leg_RED_reproduced=True,formal_execution=False),indent=2)+'\n')
for p in B.glob('*.log'):assert not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',p.read_text())
print('Actual four-leg RED and independent aborted/no-prepared/retainedSource/old resources PASS')
