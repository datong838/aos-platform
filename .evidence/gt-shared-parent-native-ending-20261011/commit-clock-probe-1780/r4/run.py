"""Three fixed isolated trials; intents are exclusive, unknown outcomes never replayed."""
import hashlib,json,pathlib,subprocess,uuid
import psycopg
from psycopg import sql
B=pathlib.Path(__file__).resolve().parent;R=pathlib.Path("/Users/ddt/work/projects/ai_agent/aos-platform")
def save(name,value):
 with (B/name).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
def docker(*args):return subprocess.check_output(['docker','--context','desktop-linux',*args],text=True,timeout=30).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
troot=pathlib.Path('/Users/ddt/work/projects/ai_agent/docs/palantier/AOS项目开发上下文/memory')
t=json.loads((troot/'receipts/tasks/gt-shared-parent-native-ending-20261011.json').read_text());leases=json.loads((troot/'leases.json').read_text())['leases'];assert t['status']=='ACTIVE' and [x for x in leases if x['task_id']==t['task_id']]==[t]
assert not (troot/'receipts/deliveries'/f"{t['task_id']}.json").exists()
scope=t['scope'];overlap=[]
for x in leases:
 if any(a==b or a.startswith(b+'/') or b.startswith(a+'/') for a in scope for b in x['scope']):overlap.append(x['task_id'])
assert overlap==[t['task_id']],overlap
save('lease-readback.json',{'task':t,'overlapping_leases':overlap,'delivery_exists':False})
st=json.loads(docker('inspect',l['name']))[0];assert st['Id']==l['container_id'] and st['Image']==l['image'] and st['State']['Running']
params=dict(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile'])
roles_sql="SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_physical_capacity_occupation_owner','aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_model_eval_issuer_owner','aos_capacity_publication_owner') ORDER BY rolname"
pending_sql="SELECT p.oid::text,p.prosrc,p.probin,p.proacl::text FROM pg_proc p WHERE p.prosrc='aos_admission_pending_relations' ORDER BY p.oid"
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster'];roles=c.execute(roles_sql).fetchall();pending=c.execute(pending_sql).fetchall();assert len(roles)==5 and all(not any(x[1:]) for x in roles) and len(pending)==1
assert json.loads(docker('image','inspect','aos-pg-core-sdk-1779:exact'))[0]['Id']=='sha256:851765e2f8107a9014019a4431240db650318edf8cbd542f1e4514993581e992'
save('build-intent.json',{'source_sha256':digest(B/'probe.c'),'recipe_sha256':digest(B/'Dockerfile'),'sdk_image':'sha256:851765e2f8107a9014019a4431240db650318edf8cbd542f1e4514993581e992','network':'none','pg_execution':False})
prior=B.parent/'r3'
assert json.loads((prior/'build-terminal.json').read_text())['exit_code']==0
image=(prior/'image-id.txt').read_text().strip();docker('image','inspect',image)
(B/'image-id.txt').open('x').write(image+'\n')
save('build-reuse.json',{'known_terminal_build':str(prior/'build-terminal.json'),'image':image,'source_sha256':digest(B/'probe.c'),'new_build_performed':False})
u=uuid.uuid4().hex;ns='test_owned_clock_'+u;lib='/tmp/aos_clock_'+u+'.so'
save('installation-intent.json',{'schema':ns,'library':lib,'container_id':l['container_id'],'cluster':l['cluster'],'database':params['dbname']})
aid=docker('create','--network','none','--name','aos-clock-artifact-'+u,(B/'image-id.txt').read_text().strip(),'/never-run');ast=json.loads(docker('inspect',aid))[0];assert ast['State']['Status']=='created' and not ast['Mounts'];save('artifact.json',{'id':aid,'status':ast['State']['Status'],'mounts':ast['Mounts']})
subprocess.run(['docker','--context','desktop-linux','cp',aid+':/clock-probe.so',str(B/'probe.so')],check=True);sha=digest(B/'probe.so');subprocess.run(['docker','--context','desktop-linux','cp',str(B/'probe.so'),l['name']+':'+lib],check=True);assert docker('exec',l['name'],'sha256sum',lib).split()[0]==sha
with psycopg.connect(**params) as c:
 c.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION aos_app').format(sql.Identifier(ns)))
 c.execute(sql.SQL("CREATE FUNCTION {}.arm(integer) RETURNS void AS {},'aos_test_clock_arm' LANGUAGE c STRICT VOLATILE PARALLEL UNSAFE SET search_path=pg_catalog").format(sql.Identifier(ns),sql.Literal(lib)))
 c.execute(sql.SQL('REVOKE ALL ON FUNCTION {}.arm(integer) FROM PUBLIC').format(sql.Identifier(ns)))
 c.execute(sql.SQL('CREATE TABLE {}.marker(label text PRIMARY KEY,xid xid8 NOT NULL)').format(sql.Identifier(ns)))
 for role in ['aos_runtime','aos_provider_capacity_occupation','aos_physical_capacity_occupation_owner']:
  assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,ns+'.arm(integer)')).fetchone()[0]
 c.commit()
save('installation-terminal.json',{'schema':ns,'binary_sha256':sha,'public_runtime_closed':True,'committed':True})
cases=[]
for mode,label in [(0,'expired'),(1,'no_delay'),(2,'after_check_delay')]:
 notices=[]
 with psycopg.connect(**params) as c:
  c.add_notice_handler(lambda n:notices.append(n.message_primary))
  c.execute('SET LOCAL synchronous_commit=on');xid=c.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
  c.execute(sql.SQL('INSERT INTO {}.marker VALUES(%s,%s::xid8)').format(sql.Identifier(ns)),(label,xid))
  c.execute(sql.SQL('SELECT {}.arm(%s)').format(sql.Identifier(ns)),(mode,))
  save(label+'-intent.json',{'xid':xid,'mode':mode,'backend_pid':c.info.backend_pid,'schema':ns})
  try:c.commit();outcome='committed';error=None
  except psycopg.Error as e:outcome='rejected';error=e.diag.message_primary;c.rollback()
  row={'label':label,'xid':xid,'outcome':outcome,'error':error,'notices':notices};save(label+'-terminal.json',row);cases.append(row)
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');states={x['label']:c.execute('SELECT pg_xact_status(%s::xid8)',(x['xid'],)).fetchone()[0] for x in cases};markers=c.execute(sql.SQL('SELECT label,xid::text FROM {}.marker ORDER BY label').format(sql.Identifier(ns))).fetchall();assert states=={'expired':'aborted','no_delay':'committed','after_check_delay':'committed'};assert sorted(markers)==sorted([(x['label'],x['xid']) for x in cases if x['outcome']=='committed']);assert c.execute(roles_sql).fetchall()==roles;assert c.execute(pending_sql).fetchall()==pending
 assert c.execute("SELECT count(*) FROM pg_auth_members WHERE member IN (SELECT oid FROM pg_roles WHERE rolname LIKE 'aos_%' AND rolname IN ('aos_physical_capacity_occupation_owner','aos_provider_capacity_issuer','aos_provider_capacity_occupation','aos_model_eval_issuer_owner','aos_capacity_publication_owner'))").fetchone()[0]==0
late=cases[2]['notices'];check=[x for x in late if x.startswith('TEST_CLOCK_CHECK:')];delay=[x for x in late if x.startswith('TEST_CLOCK_DELAY_DONE:')];comm=[x for x in late if x.startswith('TEST_CLOCK_COMMITTED:')];assert len(check)==len(delay)==len(comm)==1
now,deadline=map(int,check[0].split(':')[1:]);done=int(delay[0].split(':')[1]);post=int(comm[0].split(':')[1]);assert now<deadline<done<=post;assert cases[0]['error']=='TEST_CLOCK_EXPIRED'
verifier=docker('exec',l['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so').split()[0];assert verifier=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e';st2=json.loads(docker('inspect',l['name']))[0];assert st2['State']['StartedAt']==st['State']['StartedAt'] and st2['RestartCount']==st['RestartCount']
source=R/'.evidence/gt-shared-parent-native-ending-20261011/backend-source-audit-r1/source/src/backend/access/transam/xact.c';body=source.read_text();start=body.index('\nCommitTransaction(void)');end=body.index('\nPrepareTransaction(void)',start);commit=body[start:end];assert commit.index('XACT_EVENT_PRE_COMMIT')<commit.index('RecordTransactionCommit();')<commit.index(': XACT_EVENT_COMMIT');save('source-order.json',{'sha256':digest(source),'precommit_before_durable_record_before_commit_callback':True,'direct_flush_timestamp_measured':False})
save('verification.json',{'status':'PRECOMMIT_CLOCK_WINDOW_COUNTEREXAMPLE_VERIFIED','cases':cases,'independent_xid_states':states,'markers':markers,'clock_order':{'check':now,'deadline':deadline,'after_delay':done,'postcommit_callback':post},'signature_and_roles_and_pending_reader_unchanged':True,'lab_not_restarted':True,'full_task_delivered':False,'execution_allowed':False,'durable_flush_timestamp_directly_measured':False})
print(json.dumps({'states':states,'clock_gap_microseconds':done-deadline,'full_task_delivered':False}))
