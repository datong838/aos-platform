import json,subprocess,secrets,hashlib
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1];S=R.parent/'aos-recovery/current159-first-05b88779fad3';J=S/'native-rehearsal-r2'
result=json.loads((E/'first-native-rehearsal159-r2.json').read_text());assert result['status']=='FIRST_FULL157_RESTORE_ORIGINAL158159_NATIVE_REHEARSAL_GREEN'
before=json.loads((J/'before-snapshot.json').read_text());after=json.loads((J/'after-159-snapshot.json').read_text());canonical=lambda x:json.dumps(x,sort_keys=True)
assert set(map(canonical,before['roles']))<=set(map(canonical,after['roles']))
assert all(after['sequences'][k]==v for k,v in before['sequences'].items())
ctx='colima-aos-extension';pg='current159-first-1579cb9f5251';x=json.loads(subprocess.check_output(['docker','--context',ctx,'inspect',pg]))[0];intent=json.loads((S/'intent.json').read_text());assert x['State']['Running'] and x['HostConfig']['NetworkMode']=='none' and x['Mounts'][0]['Name']==intent['volume'] and x['Image']==intent['source_image']
program="""import psycopg,json
with psycopg.connect(host='/pgsocket',user='aos_app',dbname='aos_current_preview_20260927') as c:
 c.read_only=True;c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]=='7694901228328955942'
 assert c.execute('SELECT version_num FROM public.alembic_version').fetchall()==[('a0v_159',)]
 assert c.execute('SELECT inet_server_addr()').fetchone()[0] is None
 assert c.execute('SELECT count(*) FROM pg_prepared_xacts').fetchone()[0]==0
 assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()').fetchone()[0]==0
 roles=c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN ('aos_model_eval_execution_owner','aos_model_eval_issuer_owner') ORDER BY rolname").fetchall()
 assert len(roles)==2 and all(not any(r[1:]) for r in roles)
 assert c.execute("SELECT count(*) FROM pg_auth_members WHERE roleid IN ('aos_model_eval_execution_owner'::regrole,'aos_model_eval_issuer_owner'::regrole) OR member IN ('aos_model_eval_execution_owner'::regrole,'aos_model_eval_issuer_owner'::regrole)").fetchone()[0]==0
 tables=c.execute("SELECT n.nspname,t.relname,t.relrowsecurity,t.relforcerowsecurity FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE t.relkind='r' AND n.nspname IN ('aos_model_eval_execution_private','aos_model_eval_issuer_private') ORDER BY 1,2").fetchall();assert len(tables)==9
 from psycopg import sql
 for schema,name,rls,force in tables:
  assert rls and force
  assert c.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(sql.Identifier(schema),sql.Identifier(name))).fetchone()[0]==0
  assert c.execute('SELECT has_schema_privilege(%s,%s,%s)',('aos_runtime',schema,'USAGE')).fetchone()[0] is False
  assert c.execute('SELECT has_table_privilege(%s,%s,%s)',('aos_runtime',schema+'.'+name,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')).fetchone()[0] is False
 for name in ('aip_model_judge_budget_reservation','aip_model_judge_budget_reservation_bucket'):
  assert c.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(name))).fetchone()[0]==0
  for privilege in ('SELECT','INSERT'):assert c.execute('SELECT has_table_privilege(%s,%s,%s)',('aos_runtime','public.'+name,privilege)).fetchone()[0] is True
  for privilege in ('UPDATE','DELETE','TRUNCATE'):assert c.execute('SELECT has_table_privilege(%s,%s,%s)',('aos_runtime','public.'+name,privilege)).fetchone()[0] is False
 for name in ('aos_model_eval_issuer_private.executor_identity','aos_model_eval_issuer_private.target_result_origin'):assert c.execute('SELECT to_regclass(%s)',(name,)).fetchone()[0] is None
 for name in ('public.read_model_executor_set_facts(text,text)','public.read_model_target_result_facts(text,text,text)'):assert c.execute('SELECT to_regprocedure(%s)',(name,)).fetchone()[0] is None
 print(json.dumps({'cluster':'7694901228328955942','version':'a0v_159','private_empty_tables':9,'judge_empty_tables':2,'private_runtime_denied':True,'new_roles_no_login_or_memberships':True,'judge_select_insert_only':True,'identity_runtime_provenance_absent':True,'other_clients':0,'prepared_transactions':0,'read_only':True}),flush=True)
 c.rollback()
"""
args=['docker','--context',ctx,'run','-i','--pull','never','--name','current159-r2-independent-'+secrets.token_hex(6),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly',result['code']['tool'],'python','-']
p=subprocess.run(args,input=program.encode(),capture_output=True,timeout=120);assert p.returncode==0,p.stderr.decode();proof=json.loads(p.stdout);proof.update(original_role_attributes_unchanged=True,original_sequences_unchanged=True,current_database_writes=0,current_migration_allowed=False,program_sha256=hashlib.sha256(program.encode()).hexdigest(),native_rehearsal_result_sha256=hashlib.sha256((E/'first-native-rehearsal159-r2.json').read_bytes()).hexdigest());(E/'first-native-rehearsal159-r2-independent.json').open('x').write(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof),flush=True)
