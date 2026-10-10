from pathlib import Path
import json,os,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010';P=R/'.evidence/gt-joint-constraint-dependency-closure-20261010';orig=json.loads((P/'current-catalog-negative-r1.json').read_text());cat=orig['catalog'];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
seeds=set('aos_physical_capacity_occupation_private.'+x for x in ['prepared_parent_debit','prepared_execution_intent','prepared_plan_risk','prepared_shared_risk_description'])
seeds.update('aos_model_eval_execution_private.'+x for x in ['manifest']);seeds.update('aos_model_eval_issuer_private.'+x for x in ['executor_certificate','shared_parent_certificate_identity_binding'])
assert seeds<=set(cat['relations']);component=set(seeds)
while True:
 prior=len(component)
 for f in cat['foreign_keys']:
  if f['relation'] in component or f['referenced_relation'] in component:component.update([f['relation'],f['referenced_relation']])
 if prior==len(component):break
triggers=[t for t in cat['triggers'] if t['relation'] in component];functions=sorted({t['function'] for t in triggers})
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=orig['identity']['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('server_version') AS version,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['readonly']=='on' and identity['cluster']==lab['cluster']
 bodies={}
 for f in functions:
  row=dict(c.execute("SELECT p.prosrc AS body,p.probin AS library,l.lanname AS language,p.prosecdef AS security_definer,p.proconfig AS config,pg_get_userbyid(p.proowner) AS owner,p.provolatile AS volatility FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=%s::regprocedure",(f,)).fetchone());row['body_sha256']=hashlib.sha256(row['body'].encode()).hexdigest();assert all(t['body_hash']==row['body_sha256'] for t in triggers if t['function']==f);bodies[f]=row
 table_triggers=c.execute("SELECT n.nspname||'.'||r.relname AS relation,t.tgname AS name,pg_get_triggerdef(t.oid) AS definition,t.tgdeferrable AS deferrable,t.tginitdeferred AS initially_deferred FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname||'.'||r.relname=ANY(%s) ORDER BY 1,2",(sorted(component),)).fetchall()
 out=dict(authority='AOS-001685',identity=identity,seed_relations=sorted(seeds),fk_only_component=sorted(component),triggers=triggers,trigger_definitions=table_triggers,functions=bodies,source_catalog_sha256=orig['catalog_sha256'],actual_event_queue_proven=False,recursive_trigger_effects_complete=False,root_provenance_verified=False,execution_allowed=False)
 (B/'trigger-effects-current-r1-1685.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(identity=identity,component=len(component),triggers=len(triggers),functions=functions),indent=2))
