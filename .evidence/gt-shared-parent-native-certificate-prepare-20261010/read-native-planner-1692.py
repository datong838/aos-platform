from pathlib import Path
import os,json,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-shared-parent-native-certificate-prepare-20261010'
surface=json.loads((B/'ri-read-surface-1691.json').read_text());comparison=json.loads((B/'all-ri-comparisons-1691.json').read_text());lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=surface['identity']['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity==surface['identity']
 signatures=sorted({x['function'] for x in surface['index_family_support']}|{x['function'] for x in surface['operator_planning']})
 ids=set()
 for signature in signatures:
  ids.add(c.execute('SELECT %s::regprocedure::oid AS oid',(signature,)).fetchone()['oid'])
 operators=sorted({x['operator_oid'] for x in comparison['bindings']})
 estimators=c.execute('SELECT oprrest::oid AS restriction,oprjoin::oid AS join FROM pg_operator WHERE oid::text=ANY(%s)',(operators,)).fetchall()
 for row in estimators:ids.update(x for x in row.values() if x)
 relations=[x['relation'] for x in surface['relations']]
 methods=c.execute("SELECT n.nspname||'.'||r.relname AS relation,a.oid::text AS am_oid,a.amname,a.amtype,a.amhandler::oid AS handler_oid,a.amhandler::regprocedure::text AS handler FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_am a ON a.oid=r.relam WHERE n.nspname||'.'||r.relname=ANY(%s) UNION SELECT i.indexrelid::regclass::text,a.oid::text,a.amname,a.amtype,a.amhandler::oid,a.amhandler::regprocedure::text FROM pg_index i JOIN pg_class r ON r.oid=i.indrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_class ir ON ir.oid=i.indexrelid JOIN pg_am a ON a.oid=ir.relam WHERE n.nspname||'.'||r.relname=ANY(%s) ORDER BY relation",(relations,relations)).fetchall()
 assert {x['relation'] for x in methods if x['amtype']=='t'}==set(relations)
 ids.update(x['handler_oid'] for x in methods);seeds=sorted(ids);functions=[];seen=set()
 while ids-seen:
  pending=sorted(ids-seen)
  rows=c.execute("SELECT p.oid,p.oid::regprocedure::text AS function,n.nspname AS schema,l.lanname AS language,p.prosrc,p.probin,p.proconfig,p.proacl::text AS acl,pg_get_userbyid(p.proowner) AS owner,p.prosecdef,p.provolatile,p.proparallel,p.proleakproof,p.prosupport::oid AS support_oid,p.prosupport::regproc::text AS planner_support,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS symbol_or_body_hash FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=ANY(%s) ORDER BY p.oid",(pending,)).fetchall()
  assert len(rows)==len(pending);functions.extend(rows);seen.update(pending);ids.update(x['support_oid'] for x in rows if x['support_oid'])
 out=dict(authority='AOS-001692',identity=identity,source_hashes={name:hashlib.sha256((B/name).read_bytes()).hexdigest() for name in ('ri-read-surface-1691.json','all-ri-comparisons-1691.json')},requested_signatures=signatures,seed_oids=seeds,access_methods=methods,functions=functions,recursive_support_oids=sorted(seen-set(seeds)),native_effects_approved=False,formal_binary_provenance_verified=False,execution_allowed=False)
 (B/'native-planner-1692.json').open('x').write(json.dumps(out,indent=2)+'\n')
 print(json.dumps(dict(signatures=len(signatures),seed_functions=len(seeds),function_closure=len(functions),recursive_support=len(seen-set(seeds)),access_method_bindings=len(methods),languages=sorted({x['language'] for x in functions}),execution_allowed=False)))
