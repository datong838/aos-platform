from pathlib import Path
import json,sys,re,hashlib,os,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api import aip_physical_capacity_occupation_authority as a
names=['occupation_account_guard_statements','occupation_eval_fact_statements','occupation_parent_debit_statements','occupation_case_binding_statements','occupation_input_binding_statements','occupation_intent_statements','occupation_judge_fact_statements','occupation_judge_parent_debit_statements','occupation_judge_intent_statements','occupation_plan_risk_statements','occupation_prepared_call_statements','occupation_target_call_statements','occupation_target_ledger_statements','occupation_shared_risk_description_statements']
funcs=[];tables=[];pieces=[]
for name in names:
 statements=getattr(a,name)();assert type(statements) is tuple
 for sql in statements:
  pieces.append(dict(generator=name,sha256=hashlib.sha256(sql.encode()).hexdigest()))
  if sql.lstrip().startswith('CREATE FUNCTION'):
   mt=re.search(r'CREATE FUNCTION\s+([\w.]+)\((.*?)\)\s+RETURNS',sql,re.S);body=re.search(r'AS\s+(\$\w*\$)(.*?)\1',sql,re.S);assert mt and body,(name,'unsupported literal CREATE shape')
   # All original artifact arguments are typed named inputs, no callback/type inference.
   args=[]
   for part in ([] if not mt[2].strip() else mt[2].split(',')):
    value=part.strip().split();assert len(value)>=2,(name,'argument shape');args.append(' '.join(value[1:]))
   signature=mt[1]+'('+','.join(args)+')';funcs.append(dict(generator=name,signature=signature,expected_body_sha256=hashlib.sha256(body[2].encode()).hexdigest()))
  if sql.lstrip().startswith('CREATE TABLE'):
   mt=re.search(r'CREATE TABLE\s+([\w.]+)',sql);assert mt;tables.append(dict(generator=name,relation=mt[1]))
base=json.loads((B/'constraint-selection-current-r3-1687.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=base['identity']['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('server_version') AS version,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity==base['identity']
 for f in funcs:
  row=c.execute("SELECT p.oid::regprocedure::text AS signature,p.prosrc AS body,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,p.proconfig AS config FROM pg_proc p WHERE p.oid=to_regprocedure(%s)",(f['signature'],)).fetchone();f['installed']=row is not None
  if row:
   f['actual_body_sha256']=hashlib.sha256(row['body'].encode()).hexdigest();f['exact_original_body_match']=f['actual_body_sha256']==f['expected_body_sha256'];f['actual_catalog']={k:v for k,v in row.items() if k!='body'}
 for t in tables:t['installed']=c.execute('SELECT to_regclass(%s) IS NOT NULL AS present',(t['relation'],)).fetchone()['present']
 out=dict(authority='AOS-001688',identity=identity,original_source_sha256=hashlib.sha256((R/'services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py').read_bytes()).hexdigest(),functions=funcs,tables=tables,generated_statement_hashes=pieces,missing_functions=[f['signature'] for f in funcs if not f['installed']],drifted_function_bodies=[f['signature'] for f in funcs if f['installed'] and not f['exact_original_body_match']],missing_tables=[t['relation'] for t in tables if not t['installed']],ddl_executed=False,full_preparation_installed=all(f['installed'] and f['exact_original_body_match'] for f in funcs) and all(t['installed'] for t in tables),finalizer_installed=False,execution_allowed=False)
 (B/'full-writer-installation-r2-1688.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['functions','tables','generated_statement_hashes']},indent=2))
