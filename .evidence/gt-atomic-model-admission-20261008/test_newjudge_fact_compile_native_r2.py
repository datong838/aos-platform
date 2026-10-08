"""Original PG compiler/ACL negative gate; all DDL is rolled back."""
from pathlib import Path
import tempfile,json,importlib.util,hashlib,subprocess
import psycopg
from psycopg.rows import dict_row
r=Path(__file__).resolve().parents[2];b=Path(__file__).resolve().parent
source=r/'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py'
s=importlib.util.spec_from_file_location('fact_artifact',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass';assert passfile.stat().st_mode&0o077==0
name='aos-capacity-publication-scram-20261006';assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',name,'--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
proof={'authority_revision':'AOS-001599','head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'stage':'native compilation+ACL+caller negative only','execution_allowed':False}
with psycopg.connect(host='127.0.0.1',port=5434,dbname='aos_test_379975a6f96d_ti4_test',user='aos_app',passfile=str(passfile),row_factory=dict_row) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7693564235776004128'
 assert c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
 proof['database']='aos_test_379975a6f96d_ti4_test';proof['cluster']='7693564235776004128'
 assert c.execute('SELECT to_regprocedure(%s) AS f',(m.JUDGE_FACT,)).fetchone()['f'] is None
 assert c.execute('SELECT to_regprocedure(%s) AS f',(m.JUDGE_ENTRY,)).fetchone()['f'] is None
 for statement in m.occupation_judge_fact_statements():c.execute(statement)
 catalog=c.execute("SELECT oid::regprocedure::text AS function,pg_get_userbyid(proowner) AS owner,prosecdef,provolatile,proconfig,proacl::text AS acl FROM pg_proc WHERE oid=ANY(ARRAY[%s::regprocedure,%s::regprocedure]) ORDER BY oid",(m.JUDGE_FACT,m.JUDGE_ENTRY)).fetchall()
 assert len(catalog)==2 and all(x['prosecdef'] and x['provolatile']=='v' and x['proconfig']==['search_path=pg_catalog'] for x in catalog)
 proof['catalog']=catalog
 grants=c.execute('SELECT has_function_privilege(%s,%s,%s) AS runtime_entry,has_function_privilege(%s,%s,%s) AS owner_fact',('aos_runtime',m.JUDGE_ENTRY,'EXECUTE',m.OWNER,m.JUDGE_FACT,'EXECUTE')).fetchone();assert all(grants.values())
 public_acl=c.execute('SELECT count(*) AS n FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.oid=ANY(ARRAY[%s::regprocedure,%s::regprocedure]) AND a.grantee=0 AND a.privilege_type=%s',(m.JUDGE_FACT,m.JUDGE_ENTRY,'EXECUTE')).fetchone()['n'];assert public_acl==0
 proof['grants']=grants;proof['public_execute']=public_acl;proof['negative_checks']=[]
 for role,org,project in [('aos_app','org-org','dev-project'),('aos_runtime','org-org','dev-project'),('aos_runtime','dev-org','dev-project')]:
  with c.transaction(force_rollback=True):
   c.execute('SET LOCAL ROLE '+role);c.execute('SELECT set_config(%s,%s,true),set_config(%s,%s,true)',('aos.org_id',org,'aos.project_id',project))
   try:c.execute("SELECT public.read_capacity_occupation_judge_fact(%s,%s::jsonb,%s::uuid,%s,%s)",(b'invalid','{}','00000000-0000-0000-0000-000000000001','missing','0'*64));raise AssertionError('invalid session admitted')
   except psycopg.errors.InsufficientPrivilege as exc:
    assert 'CAPACITY_JUDGE_FACT_CALLER_REQUIRED' in str(exc);proof['negative_checks'].append({'role':role,'tenant':[org,project],'sqlstate':exc.sqlstate,'reason':'strict session-user rejection'})
 c.rollback()
 # Known rollback, then read-only reconciliation. Do not leave an installation.
 c.execute('SET TRANSACTION READ ONLY')
 assert c.execute('SELECT to_regprocedure(%s) AS f',(m.JUDGE_FACT,)).fetchone()['f'] is None
 assert c.execute('SELECT to_regprocedure(%s) AS f',(m.JUDGE_ENTRY,)).fetchone()['f'] is None
 proof['ddl_rollback_verified']=True;proof['limitations']=['No actual SCRAM occupation login positive','New Judge Source/parent graph SQL body remains positive-unverified','Rule trust/currentness and original full fee guard remain joint Owner prerequisites','No finalizer/Intent integration or formal installation']
(b/'newjudge-fact-native-compile-r2.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'compiled':len(catalog),'negative_checks':len(proof['negative_checks']),'ddl_rollback_verified':True},ensure_ascii=False))
