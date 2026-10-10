from pathlib import Path
import sys,os,json,hashlib
import psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-joint-constraint-dependency-closure-20261010';sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_physical_capacity_joint_catalog import JointCatalog,ForeignKey,Trigger,joint_constraint_closure,JointCatalogRejected
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());prior=json.loads((R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010/native-r22/result-r22.json').read_text());assert prior['pytest_exit']==0
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=prior['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');ident=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert ident['cluster']==lab['cluster'] and ident['readonly']=='on'
 rels=c.execute("SELECT n.nspname||'.'||r.relname AS name FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace WHERE r.relkind IN ('r','p') AND (n.nspname='public' OR n.nspname LIKE 'aos_%') ORDER BY 1").fetchall();relations=frozenset(x['name'] for x in rels)
 fk=c.execute("""SELECT n.nspname||'.'||r.relname||'.'||k.conname AS key,n.nspname||'.'||r.relname AS relation,np.nspname||'.'||rp.relname AS referenced_relation FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_class rp ON rp.oid=k.confrelid JOIN pg_namespace np ON np.oid=rp.relnamespace WHERE k.contype='f' AND (n.nspname='public' OR n.nspname LIKE 'aos_%') ORDER BY 1""").fetchall()
 ts=c.execute("""SELECT n.nspname||'.'||r.relname||'.'||t.tgname AS key,n.nspname||'.'||r.relname AS relation,format('%I.%I(%s)',nf.nspname,p.proname,pg_get_function_identity_arguments(p.oid)) AS function,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS body_hash,t.tgenabled='O' AS enabled,t.tgisinternal AS internal FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace nf ON nf.oid=p.pronamespace WHERE n.nspname='public' OR n.nspname LIKE 'aos_%' ORDER BY 1""").fetchall()
 catalog=JointCatalog(relations,tuple(ForeignKey(**dict(x)) for x in fk),tuple(Trigger(**dict(x)) for x in ts));seeds=frozenset('aos_physical_capacity_occupation_private.'+x for x in ['prepared_parent_debit','prepared_execution_intent','prepared_plan_risk','prepared_shared_risk_description'])
 try:joint_constraint_closure(catalog,seeds,())
 except JointCatalogRejected as exc:rejection=str(exc)
 else:raise AssertionError('unreviewed installed effects accepted')
 assert rejection=='TRIGGER_EFFECT_REQUIRED'
 raw=json.dumps(dict(relations=sorted(relations),foreign_keys=fk,triggers=ts),sort_keys=True,separators=(',',':')).encode()
 output=dict(identity=ident,relation_count=len(relations),foreign_key_count=len(fk),trigger_count=len(ts),catalog_sha256=hashlib.sha256(raw).hexdigest(),reviewed_effect_contracts=0,actual_current_catalog_rejection=rejection,execution_allowed=False,actual_event_queue_proven=False,finalizer_implemented=False,module_hash=hashlib.sha256((R/'services/aos-api/aos_api/aip_physical_capacity_joint_catalog.py').read_bytes()).hexdigest(),catalog=dict(relations=sorted(relations),foreign_keys=fk,triggers=ts))
 (B/'current-catalog-negative-r1.json').open('x').write(json.dumps(output,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items() if k not in ['catalog','module_hash']}))
