"""Independent read-only durable ledger proof, original algorithm and exact hashes."""
import ast,hashlib,json,os,re,subprocess,tempfile,sys
from datetime import UTC,datetime
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
os.environ['PGPASSFILE']=str(passfile)
container=subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect','aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()
assert container=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
p=Path('services/aos-api/aos_api/aip_budget_reservation_store.py')
old=ast.parse(subprocess.check_output(['git','show','9bc6ef7b1d97ce56aca6b8711e60cb8700ddafc2:'+str(p)],cwd=ROOT,text=True))
new=ast.parse((ROOT/p).read_text())
def methods(tree):return {n.name:n for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='AipBudgetReservationStore' for n in c.body if isinstance(n,ast.FunctionDef)}
a=methods(old);b=methods(new)
class SqlIndent(ast.NodeTransformer):
    def visit_Constant(self,node):
        if isinstance(node.value,str) and '\n' in node.value:
            node.value=re.sub(r'\n[ \t]+','\n',node.value)
        return node
def normalized(body):return ast.dump(SqlIndent().visit(ast.Module(body=body,type_ignores=[])))
w=next(n for n in a['reserve'].body if isinstance(n,ast.With))
assert normalized(w.body)==normalized(b['_reserve_in_transaction'].body)
assert all(ast.dump(n)==ast.dump(b[name]) for name,n in a.items() if name!='reserve')
assert all(not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute) or n.func.attr not in ('commit','rollback','close','connect','_connect_factory') for n in ast.walk(b['reserve_in_transaction']))
proof_log=OUT/(sys.argv[1] if len(sys.argv)>1 else 'green-r1.log')
schemas=re.findall(r'Retained isolated budget schema: (ar2_budget_[a-f0-9]{32})',proof_log.read_text())
if len(sys.argv)>1:
    assert '37 passed' in proof_log.read_text()
    schemas=schemas[-15:]
assert len(schemas)==len(set(schemas))==15
records=[]
with psycopg.connect('postgresql://aos_app@127.0.0.1:5434/aos_meta',row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
    for schema in schemas:
        counts=[];canary=[]
        for table in ('aip_capability_invocation','aip_budget_reservation','aip_budget_reservation_bucket','aip_budget_reservation_event'):
            query=sql.SQL('SELECT count(*) AS n FROM {}.{} WHERE org_id=%s AND project_id=%s').format(sql.Identifier(schema),sql.Identifier(table))
            counts.append(conn.execute(query,('org-org','dev-project')).fetchone()['n'])
            canary.append(conn.execute(query,('dev-org','dev-project')).fetchone()['n'])
        assert canary==[0,0,0,0]
        buckets=conn.execute(sql.SQL('SELECT count(*) AS n,coalesce(sum(held_minor),0) AS held,coalesce(sum(submitted_minor+settled_minor+unknown_minor),0) AS other FROM {}.aip_budget_bucket').format(sql.Identifier(schema))).fetchone()
        if counts==[1,1,3,1]:
            row=conn.execute(sql.SQL('SELECT state,upper_bound_minor FROM {}.aip_budget_reservation').format(sql.Identifier(schema))).fetchone()
            invocation=conn.execute(sql.SQL('SELECT state FROM {}.aip_capability_invocation').format(sql.Identifier(schema))).fetchone()
            assert row['state']=='held' and invocation['state']=='prepared'
            assert buckets=={'n':3,'held':row['upper_bound_minor']*3,'other':0}
        else:
            assert counts==[0,0,0,0] and buckets=={'n':0,'held':0,'other':0}
        records.append({'schema':schema,'counts':counts,'canary':canary,'buckets':{k:int(v) for k,v in buckets.items()}})
assert sum(r['counts']==[1,1,3,1] for r in records)==1
files=[p,Path('services/aos-api/tests/aip/test_budget_caller_transaction_pg.py'),Path('services/aos-api/tests/aip/test_aip_budget_reservation_pg.py'),Path('services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py')]
files += [f.relative_to(ROOT) for f in OUT.glob('*.log')]+[Path('.evidence/gt-budget-caller-transaction-20261007/plan.md'),Path('.evidence/gt-content-fixture-clock-20261007/plan.md')]
report={'proof_log':proof_log.name,'verified_at':datetime.now(UTC).isoformat(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'container_id':container,'cluster_id':'7693564235776004128','readonly':True,'schemas':records,'original_algorithm_identical_except_SQL_newline_indentation':True,'other_original_methods_identical':True,'caller_api_no_transaction_lifecycle_calls':True,'hashes':{str(f):hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'formal_resources_changed':False,'shared_physical_budget_intent_complete':False,'full_goal_complete':False}
(OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('Readonly verified 15 retained schemas: one committed hold, fourteen empty; canary zero; original algorithm preserved.')
