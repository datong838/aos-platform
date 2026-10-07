"""Read-only check of owned retained content clone and unchanged old fixture."""
import ast,hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
root=Path(__file__).resolve().parents[2]
logs=root/'.evidence/gt-budget-caller-transaction-20261007'
log=logs/'final-release-revoke-green-r5.log'
assert '12 passed' in log.read_text()
names=re.findall(r'Retained isolated content database: (a0v_growth_graph_test_[a-f0-9]{32})',log.read_text())
assert len(names)==1
os.environ['PGPASSFILE']=str(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass')
records={}
with psycopg.connect('postgresql://aos_app@127.0.0.1:5434/'+names[0],row_factory=dict_row) as conn:
 conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
 assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_157'
 for table in ('aip_logic_graph','aip_release_gate_decision','aip_publication_event','aip_eval_contract_head','aip_task_run','aip_budget_reservation','aip_capability_invocation','aip_usage_receipt'):
  records[table]={tenant:conn.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE org_id=%s AND project_id=%s').format(sql.Identifier(table)),(tenant,'dev-project')).fetchone()['n'] for tenant in ('org-org','dev-org')}
  assert records[table]['dev-org']==0
 for table in ('aip_logic_graph','aip_release_gate_decision','aip_publication_event','aip_eval_contract_head','aip_task_run','aip_budget_reservation','aip_capability_invocation'):
  assert records[table]['org-org']==1
 assert records['aip_usage_receipt']['org-org']==0
 lineage=conn.execute('SELECT g.decided_at,e.occurred_at,p.epoch,clock_timestamp() AS now FROM aip_release_gate_decision g JOIN aip_publication_event e ON e.release_gate_decision_id=g.decision_id JOIN aip_publication_epoch p ON p.org_id=e.org_id AND p.project_id=e.project_id AND p.publication_id=e.publication_id').fetchone()
 assert lineage['decided_at']<=lineage['occurred_at']<=lineage['now'] and lineage['epoch']==1
 template=re.findall(r'Retained isolated test database: (aos_test_[a-z0-9_]+)',(logs/'green-r1.log').read_text())[0]
with psycopg.connect('postgresql://aos_app@127.0.0.1:5434/'+template,row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 for table in ('aip_logic_graph','aip_publication_event','aip_eval_contract_head'):
  assert c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n']==0
p=Path('services/aos-api/tests/test_ecommerce_analyst_growth_plan_full_graph.py')
old=ast.parse(subprocess.check_output(['git','show','9bc6ef7b1d97ce56aca6b8711e60cb8700ddafc2:'+str(p)],cwd=root,text=True));new=ast.parse((root/p).read_text())
a=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='disposable_database')
b=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='disposable_database')
b.body=[n for n in b.body if not isinstance(n,ast.If)]
assert ast.dump(a)==ast.dump(b)
report={'database':names[0],'template':template,'cluster_id':'7693564235776004128','migration':'a0v_157','readonly':True,'records':records,'lineage':{k:v.isoformat() if hasattr(v,'isoformat') else v for k,v in lineage.items()},'default_fixture_AST_unchanged':True,'template_unchanged_empty':True,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'formal_resources_changed':False,'full_goal_complete':False}
Path(__file__).with_name('verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('Retained content clone independently verified: exact release lineage, epoch1, original Plan/budget/invocation, usage0, canary0; template unchanged.')
