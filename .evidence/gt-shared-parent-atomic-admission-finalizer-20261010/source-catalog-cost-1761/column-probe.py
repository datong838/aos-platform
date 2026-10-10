from pathlib import Path
import json,time,statistics,hashlib
import psycopg
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
params=dict(host='127.0.0.1',port=lab['port'],dbname='aos_test_7c4f2f6b4aa8_ti4_test',user='aos_app',passfile=lab['passfile'])
prefix="SELECT count(DISTINCT (c.oid,a.attname)) FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped AND "
original="(has_column_privilege(%s::oid,c.oid,a.attnum,'INSERT,REFERENCES') OR has_column_privilege(%s::oid,c.oid,a.attnum,'UPDATE'))"
merged="has_column_privilege(%s::oid,c.oid,a.attnum,'INSERT,REFERENCES,UPDATE')"
rows=[]
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 oid=c.execute("SELECT oid FROM pg_roles WHERE rolname='aos_capacity_publication_owner'").fetchone()[0]
 body=c.execute("SELECT prosrc FROM pg_proc WHERE oid='aos_capacity_publication_private.require_original_fact_boundary()'::regprocedure").fetchone()[0]
 assert body.count("has_column_privilege(owner_oid,c.oid,a.attnum,'INSERT,REFERENCES')") == 2
 mismatch_sql="SELECT count(*),count(*) FILTER(WHERE "+original+" IS DISTINCT FROM "+merged+") FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped"
 columns,mismatches=c.execute(mismatch_sql,(oid,oid,oid)).fetchone();assert mismatches==0
 for variant in ['original','merged','merged','original']:
  sql=prefix+(original if variant=='original' else merged);args=(oid,oid) if variant=='original' else (oid,)
  for n in range(10):
   start=time.perf_counter();count=c.execute(sql,args).fetchone()[0];rows.append(dict(variant=variant,count=count,seconds=time.perf_counter()-start))
 assert {r['count'] for r in rows}=={5}
 assert c.execute("SELECT prosrc FROM pg_proc WHERE oid='aos_capacity_publication_private.require_original_fact_boundary()'::regprocedure").fetchone()[0]==body;c.rollback()
data=dict(authority='AOS-001761',scope='read-only same native catalog snapshot built-in column privilege predicates only',columns_compared=columns,mismatches=mismatches,expected_original_count=5,samples=rows,median_seconds={v:statistics.median(r['seconds'] for r in rows if r['variant']==v) for v in ['original','merged']},original_routine_sha256=hashlib.sha256(body.encode()).hexdigest(),original_routine_unchanged=True,product_modified=False,all_possible_acl_drift_proven=False,whole_source_timing_recovered=False,source_issued=False,execution_allowed=False)
with (OUT/'column-result.json').open('x') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps({k:data[k] for k in ['columns_compared','mismatches','median_seconds']}))
