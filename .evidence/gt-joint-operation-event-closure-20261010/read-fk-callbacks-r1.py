from pathlib import Path
import os,json,sys,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-joint-operation-event-closure-20261010'
base=json.loads((B/'current-events-negative-r1.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=base['identity']['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('server_version') AS version,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity==base['identity']
 rows=c.execute("""SELECT n.nspname||'.'||r.relname||'.'||k.conname AS key,x.kind,x.opoid::text AS operator_oid,o.oprname,onsp.nspname AS operator_schema,p.oid::regprocedure::text AS callback,pn.nspname AS callback_schema,l.lanname AS language,p.probin AS library,p.prosrc AS body,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,p.provolatile AS volatility FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace CROSS JOIN LATERAL (SELECT 'pk_fk' AS kind,unnest(k.conpfeqop) AS opoid UNION ALL SELECT 'pk_pk',unnest(k.conppeqop) UNION ALL SELECT 'fk_fk',unnest(k.conffeqop)) x JOIN pg_operator o ON o.oid=x.opoid JOIN pg_namespace onsp ON onsp.oid=o.oprnamespace JOIN pg_proc p ON p.oid=o.oprcode JOIN pg_namespace pn ON pn.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE k.contype='f' AND (n.nspname='public' OR n.nspname LIKE 'aos_%') ORDER BY key,x.kind,x.opoid""").fetchall()
 assert {x['key'] for x in rows}==set(base['actions'])
 for x in rows:x['body_sha256']=hashlib.sha256(x['body'].encode()).hexdigest()
 callbacks={x['callback']: {k:x[k] for k in ['callback_schema','language','library','owner','security_definer','volatility','body_sha256']} for x in rows}
 out=dict(identity=identity,foreign_key_count=len(base['actions']),operator_bindings=len(rows),callbacks=callbacks,non_pg_internal_callbacks=[k for k,v in callbacks.items() if v['callback_schema']!='pg_catalog' or v['language']!='internal'],bindings=rows,read_only_catalog_lookup=True,callbacks_executed=False,binary_provenance_verified=False,casts_collations_complete=False,formal_installation_approved=False,execution_allowed=False)
 (B/'fk-callbacks-r1.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='bindings'},indent=2))
