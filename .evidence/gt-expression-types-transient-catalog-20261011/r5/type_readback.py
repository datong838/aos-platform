import json,hashlib
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
B=Path(__file__).resolve().parent; R=B.parents[2]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text()); run=json.loads((B/'result-r2.json').read_text()); records=json.loads((B/'typed-records.json').read_text())
assert records and all(all(type(v) is int and v>=0 for v in row) for row in records)
fids=sorted({r[1] for r in records if r[1]}); tids=sorted({v for r in records for v in r[2:] if v})
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=run['databases'][0],passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('BEGIN READ ONLY')
 funcs=c.execute('SELECT oid,oid::regprocedure::text AS signature,prorettype,proargtypes::text AS declared_arg_types,prosecdef,prolang::regtype::text AS language_oid FROM pg_proc WHERE oid=ANY(%s::oid[]) ORDER BY oid',(fids,)).fetchall()
 types=c.execute('SELECT oid,oid::regtype::text AS type_name,typtype,typelem,typbasetype,typrelid FROM pg_type WHERE oid=ANY(%s::oid[]) ORDER BY oid',(tids,)).fetchall(); c.rollback()
x={'records':len(records),'function_oids':len(fids),'retained_functions':funcs,'missing_function_oids_after_rollback':sorted(set(fids)-{r['oid'] for r in funcs}),'observed_type_oids':len(tids),'retained_types':types,'missing_type_oids_after_rollback':sorted(set(tids)-{r['oid'] for r in types}),'records_sha256':hashlib.sha256((B/'typed-records.json').read_bytes()).hexdigest(),'full_native_closure':False,'formal_root_authorized':False,'limits':['Expression args are planned expression types, not every native fmgr argument','Rollback removes temporary function and composite type identities; absent identities are not reconstructed','No proof of unvisited branches, implicit native callbacks, natural COMMIT or formal business acceptance']}
(B/'type-binding-readback.json').write_text(json.dumps(x,indent=2)+'\n'); print(json.dumps({k:v for k,v in x.items() if k not in ('retained_functions','retained_types','limits')}))
