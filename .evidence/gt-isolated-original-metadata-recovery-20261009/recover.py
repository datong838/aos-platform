"""Frozen original installation recovery in one explicitly owned isolated lab."""
import ast,hashlib,importlib.util,json,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

REPO=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
DB='aos_test_965e5441744f_ti4_test';CLUSTER='7693564235776004128';HEAD='1b35760e26faf9c9c4905973a179922a0ef47ac8'
MODE=sys.argv[1];assert MODE in ('red','rehearse','apply','verify','rollback')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()==HEAD
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect','aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
s=importlib.util.spec_from_file_location('mc',REPO/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules['mc']=m;s.loader.exec_module(m)
assert m.load_authority()['project_revision']=='AOS-001595'
task=m.read_json(m.DEFAULT_PATHS.receipts_path/'tasks'/'gt-isolated-original-metadata-recovery-20261009.json');assert task['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and task['status']=='ACTIVE'
assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x.get('task_id')==task['task_id']]==[task]
assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
PASS=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass';assert PASS.stat().st_mode&0o077==0
sys.path.insert(0,str(REPO/'services/aos-api'))
from aos_api.aip_model_eval_action import ModelEvalActionGuard,ModelEvalActionBlocked,_OBJECT as MODEL_OBJECT
from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard,ProviderCapacityActionBlocked
from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard
from aos_api.tenant_scope import TenantScope,apply_transaction_scope
SCOPE=TenantScope('org-org','dev-project')
GUARDS=[ModelEvalActionGuard,ProviderCapacityActionGuard,ProviderCapacitySourceActionGuard]
OBJECTS=[MODEL_OBJECT,ProviderCapacityActionGuard.object_snapshot,ProviderCapacitySourceActionGuard.object_snapshot]
MIGRATIONS=[('a0v_133_model_eval_request.py','bfd15fdcfae6a6843fe9fd6fa50722d4b3cc66fe6780afe30f0c619ed5c88533','model_eval_metadata_a0v133'),('a0v_146_provider_capacity_action.py','dad16389f49a76375cc9da554ba59287f8e6428b90af94352628bb764d3f7bad','provider_capacity_metadata_a0v146'),('a0v_148_provider_capacity_source_action.py','a161ab74de871465d995cd094f7c148c64d4bc98ff7dfdc146250146b6b8a042','provider_capacity_metadata_a0v148')]
INSERTS=[];FUNCTIONS=[]
for (filename,digest,function),obj in zip(MIGRATIONS,OBJECTS):
 p=REPO/'services/aos-api/alembic/versions'/filename;assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
 sqls=[x.args[0].value for x in ast.walk(ast.parse(p.read_text())) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='execute' and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str)]
 matches=[x for x in sqls if x.startswith('INSERT INTO public.meta_object_type')];assert len(matches)==1 and obj['id'] in matches[0] and ';' not in matches[0];INSERTS.append(matches[0])
 definition=next(x for x in sqls if x.startswith('CREATE FUNCTION public.'+function+'()'))
 body=definition.split('AS $$',1)[1].rsplit('$$',1)[0];FUNCTIONS.append((function,body))

def connect():
 c=psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=DB,passfile=str(PASS),row_factory=dict_row)
 c.isolation_level=psycopg.IsolationLevel.SERIALIZABLE
 c.execute("SET LOCAL lock_timeout='3s'")
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==CLUSTER
 assert c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_158'
 assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()['n']==0
 return c

def fingerprint(c):
 tables=[x['name'] for x in c.execute("SELECT format('%I.%I',n.nspname,t.relname) AS name FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE t.relkind='r' AND (n.nspname='public' OR n.nspname LIKE 'aos_capacity%') ORDER BY 1").fetchall()]
 rows={}
 for table in tables:
  result=c.execute("SELECT row_to_json(t)::text AS row FROM "+table+" t").fetchall();data=sorted(x['row'] for x in result)
  rows[table]={'count':len(data),'sha256':hashlib.sha256(json.dumps(data,ensure_ascii=False).encode()).hexdigest()}
 return rows

def objects(c):return c.execute('SELECT id,name,description,published,properties,required_markings FROM meta_object_type WHERE id=ANY(%s) ORDER BY id',([x['id'] for x in OBJECTS],)).fetchall()

def check_install(c):
 for name,body in FUNCTIONS:
  found=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure',('public.'+name+'()',)).fetchone();assert found['prosrc']==body
  triggers=c.execute("SELECT tgname FROM pg_trigger WHERE tgfoid=%s::regprocedure AND tgrelid IN ('public.meta_object_type'::regclass,'public.meta_action_type'::regclass) AND tgenabled='O'",('public.'+name+'()',)).fetchall();assert len(triggers)==2
 for guard in GUARDS:
  action=guard.action_snapshot if hasattr(guard,'action_snapshot') else __import__('aos_api.aip_model_eval_action',fromlist=['_ACTION'])._ACTION
  found=c.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s',(action['id'],)).fetchone()
  expected={'id':action['id'],'name':action['name'],'object_type':action['objectType'],'parameters':action['parameters'],'required_markings':action['requiredMarkings'],'submission_criteria':action['submissionCriteria']};assert found==expected

def run_guards(c,missing):
 c.execute('SAVEPOINT original_runtime');apply_transaction_scope(c,SCOPE)
 result=[]
 for guard in GUARDS:
  c.execute('SAVEPOINT one_guard')
  try:
   value=guard.read_metadata(c)
   assert not missing
   result.append({'guard':guard.__name__,'outcome':'PASS','snapshot':value})
  except (ModelEvalActionBlocked,ProviderCapacityActionBlocked) as e:
   assert missing and 'OBJECT_TYPE_DRIFTED' in str(e)
   result.append({'guard':guard.__name__,'outcome':'EXPECTED_DENIAL','reason':str(e)})
  finally:c.execute('ROLLBACK TO SAVEPOINT one_guard')
 c.execute('ROLLBACK TO SAVEPOINT original_runtime');return result

def assert_old_metadata_unchanged(c, baseline):
 rows=c.execute("SELECT row_to_json(t)::text AS row FROM public.meta_object_type t WHERE id<>ALL(%s)",([x['id'] for x in OBJECTS],)).fetchall()
 data=sorted(x['row'] for x in rows)
 assert {'count':len(data),'sha256':hashlib.sha256(json.dumps(data,ensure_ascii=False).encode()).hexdigest()}==baseline['public.meta_object_type']

def restored(c):
 assert sorted(objects(c),key=lambda x:x['id'])==sorted(OBJECTS,key=lambda x:x['id'])
 result=run_guards(c,False)
 for obj,guard in zip(OBJECTS,GUARDS):
  c.execute('SAVEPOINT negative_drift');c.execute('UPDATE meta_object_type SET name=%s WHERE id=%s',('isolated negative drift',obj['id']))
  apply_transaction_scope(c,SCOPE)
  try:guard.read_metadata(c)
  except (ModelEvalActionBlocked,ProviderCapacityActionBlocked) as e:assert 'OBJECT_TYPE_DRIFTED' in str(e)
  else:raise AssertionError('original guard accepted drift')
  finally:c.execute('ROLLBACK TO SAVEPOINT negative_drift')
 return result

with connect() as c:
 check_install(c);before=fingerprint(c)
 if MODE in ('red','rollback'):
  if MODE=='rollback':assert before==json.loads((OUT/'red.json').read_text())['baseline']
  assert objects(c)==[];guards=run_guards(c,True);payload={'mode':MODE,'baseline':before,'guards':guards,'objects':objects(c)};c.rollback()
 elif MODE=='verify':
  saved=json.loads((OUT/'red.json').read_text())['baseline'];guards=restored(c);assert_old_metadata_unchanged(c,saved);after=fingerprint(c)
  assert {k:v for k,v in saved.items() if k!='public.meta_object_type'}=={k:v for k,v in after.items() if k!='public.meta_object_type'}
  assert after['public.meta_object_type']['count']==saved['public.meta_object_type']['count']+3
  payload={'mode':MODE,'guards':guards,'objects':objects(c),'after':after,'all_other_tables_unchanged':True};c.rollback()
 else:
  saved=json.loads((OUT/'red.json').read_text())['baseline'];assert before==saved and objects(c)==[]
  c.execute('LOCK TABLE public.meta_object_type,public.meta_action_type IN SHARE ROW EXCLUSIVE MODE')
  if MODE=='apply':
   with (OUT/'apply-attempt.json').open('x') as h:json.dump({'head':HEAD,'authority':'AOS-001595','database':DB,'cluster':CLUSTER,'original_insert_hashes':[hashlib.sha256(x.encode()).hexdigest() for x in INSERTS]},h)
  for sql in INSERTS:c.execute(sql)
  guards=restored(c);assert_old_metadata_unchanged(c,before);after=fingerprint(c)
  assert {k:v for k,v in before.items() if k!='public.meta_object_type'}=={k:v for k,v in after.items() if k!='public.meta_object_type'}
  assert after['public.meta_object_type']['count']==before['public.meta_object_type']['count']+3
  payload={'mode':MODE,'before':before,'after':after,'objects':objects(c),'guards':guards,'all_other_tables_unchanged':True,'commit':MODE=='apply'}
  if MODE=='apply':c.commit()
  else:c.rollback()
payload.update(observed_at=datetime.now(timezone.utc).isoformat(),database=DB,cluster=CLUSTER,head=HEAD)
(OUT/(MODE+'.json')).write_text(json.dumps(payload,ensure_ascii=False,default=str,indent=2)+'\n');print(json.dumps({'mode':MODE,'guards':[x['outcome'] for x in payload['guards']],'tables_checked':len(payload.get('baseline',payload.get('after',{}))),'commit':payload.get('commit',False)},ensure_ascii=False))
