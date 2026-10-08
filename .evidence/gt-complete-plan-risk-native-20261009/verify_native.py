"""Independent reconciliation and private-table security audit."""
import json,subprocess,hashlib,ast,re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[1];lab=json.loads((B/'lab.json').read_text());db=json.loads((B/'native-r2-result.json').read_text())['database']
plan=json.loads((B/'complete-plan-risk.json').read_text())['plan'];assert len(plan['immutable']['legs'])==4 and plan['physicalPreparedRequests']==plan['physicalPreparedTokens']==0
whole=json.loads((R/'.evidence/gt-judge-call-authority-20261008/complete-plan-risk-r2-whole-plan-proof.json').read_text());assert whole['source_commit_denial']['actual_commit_rejected'] and whole['independent_xact_status']=='aborted'
xid=plan['immutable']['callerXid'];assert xid==whole['source_commit_denial']['xid']
before=json.loads((R/'.evidence/gt-source-newjudge-native-lab-20261009/preflight.json').read_text())['old_containers'];after=json.loads(subprocess.check_output(['docker','--context',lab['context'],'inspect',*[x['Id'] for x in before]],text=True));assert len(before)==len(after)
for a,b in zip(after,before):
 for k,v in dict(Id=a['Id'],name=a['Name'],started=a['State']['StartedAt'],mounts=a['Mounts'],ports=a['HostConfig']['PortBindings']).items():assert b[k]==v
with psycopg.connect(host='127.0.0.1',port=5436,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==lab['cluster']
 status=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(xid,)).fetchone()['state'];assert status=='aborted'
 counts={t:c.execute('SELECT count(*) AS n FROM aos_physical_capacity_occupation_private.'+t).fetchone()['n'] for t in ('account_guard','prepared_parent_debit','prepared_execution_intent','prepared_plan_risk')};assert counts==dict(account_guard=1,prepared_parent_debit=0,prepared_execution_intent=0,prepared_plan_risk=0)
 race=json.loads((R/'.evidence/gt-atomic-model-admission-20261008/source-newjudge-complete-plan-risk-r2-guard-race.json').read_text());assert c.execute('SELECT version FROM aos_physical_capacity_occupation_private.account_guard').fetchone()['version']==race['writer']['version']
 catalog=c.execute("SELECT relrowsecurity,relforcerowsecurity,pg_get_userbyid(relowner) AS owner,has_table_privilege('aos_runtime',oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS runtime_privilege FROM pg_class WHERE oid='aos_physical_capacity_occupation_private.prepared_plan_risk'::regclass").fetchone();assert catalog==dict(relrowsecurity=True,relforcerowsecurity=True,owner='aos_physical_capacity_occupation_owner',runtime_privilege=False)
 triggers=c.execute("SELECT tgname,tgdeferrable,tginitdeferred FROM pg_trigger WHERE tgrelid='aos_physical_capacity_occupation_private.prepared_plan_risk'::regclass AND NOT tgisinternal ORDER BY tgname").fetchall();assert len(triggers)==3 and any(t['tgdeferrable'] and t['tginitdeferred'] for t in triggers)
 source=c.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.source_publication').fetchone()['n'];assert source==1
 role=c.execute("SELECT rolcanlogin AS login,(SELECT count(*) FROM pg_auth_members WHERE member=r.oid OR roleid=r.oid) AS memberships FROM pg_roles r WHERE rolname='aos_provider_capacity_occupation'").fetchone();assert role==dict(login=False,memberships=0)
 assert c.execute("SELECT to_regprocedure('public.prepare_capacity_plan_risk(bytea,jsonb,uuid,text,text,uuid,text,text,uuid)') AS fn").fetchone()['fn'] is None
(B/'independent.json').write_text(json.dumps(dict(database=db,xid=xid,status=status,counts=counts,private_catalog=catalog,triggers=triggers,source_retained=source,role=role,old_resources_unchanged=True,actual_inflight_added=0,full_goal=False),indent=2)+'\n')
p=R/'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py';ast.parse(p.read_text());old=subprocess.check_output(['git','show','HEAD:'+str(p.relative_to(R))],cwd=R,text=True);assert p.read_text().split('PLAN_FACT =',1)[0].rstrip()==old.rstrip()
for log in B.glob('*.log'):assert not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',log.read_text())
(B/'static-final.json').write_text(json.dumps(dict(AST='PASS',old_compilers_unchanged=True,code_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2)+'\n');print('Independent original four-leg risk/zero-inflight/aborted/private ACL/Source and old service preservation PASS')
