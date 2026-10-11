from pathlib import Path
import json,hashlib,subprocess,re
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent;R=B.parents[2]
prior=json.loads((B.parent/'aggregate-group-source-1807/independent-readback.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
st=json.loads(subprocess.check_output(['docker','--context','desktop-linux','inspect',lab['name']],text=True))[0];assert st['Id']==lab['container_id'] and st['Image']==lab['image'] and st['State']['Running']
seeds=[x for x in prior['observed_functions'] if x['prosecdef']];assert len(seeds)==4
rows=[]
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=prior['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 for seed in seeds:
  row=c.execute('''SELECT p.oid,p.oid::regprocedure::text AS signature,p.prosrc,p.prosecdef,p.proconfig,p.proowner::regrole::text AS owner,n.nspname AS schema FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.oid=%s''',(seed['oid'],)).fetchone();assert row
  source=row.pop('prosrc');row['source_sha256']=hashlib.sha256(source.encode()).hexdigest()
  for k in ['signature','owner','source_sha256','prosecdef','proconfig']:assert row[k]==seed[k],(k,row,seed)
  assert row['proconfig']==['search_path=pg_catalog']
  row['acl']=c.execute('''SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s ORDER BY 1,2''',(seed['oid'],)).fetchall()
  row['effective_execute']={r:c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(r,seed['oid'])).fetchone()['allowed'] for r in ['aos_runtime','aos_physical_capacity_occupation_owner','aos_model_eval_issuer_owner']}
  row['schema_create']={r:c.execute("SELECT has_schema_privilege(%s,%s,'CREATE') AS allowed",(r,row['schema'])).fetchone()['allowed'] for r in ['aos_runtime','aos_physical_capacity_occupation_owner','aos_model_eval_issuer_owner']}
  row['owner_flags']=c.execute('SELECT rolcanlogin,rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(row['owner'],)).fetchone()
  row['owner_memberships']=c.execute('SELECT roleid::regrole::text AS role,member::regrole::text AS member FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(row['owner'],row['owner'])).fetchall()
  row['lexical_review_lines']=[{'line':i,'text':line.strip()} for i,line in enumerate(source.splitlines(),1) if re.search(r'\b(EXECUTE|LOAD|set_config)\b',line,re.I)]
  (B/(str(seed['oid'])+'.sql')).write_text(source)
  rows.append(row)
 c.rollback()
result={'database':prior['database'],'cluster':lab['cluster'],'functions':rows,'read_only':True,'full_reachable_closure':False,'execution_authorized':False}
(B/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps([{'signature':x['signature'],'acl':x['acl'],'effective_execute':x['effective_execute'],'owner_flags':x['owner_flags'],'memberships':x['owner_memberships'],'lexical_lines':len(x['lexical_review_lines'])} for x in rows]))
