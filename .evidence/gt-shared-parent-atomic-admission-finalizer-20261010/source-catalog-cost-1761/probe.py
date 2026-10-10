from pathlib import Path
import json,hashlib,time,statistics,subprocess,re
import psycopg
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
params=dict(host='127.0.0.1',port=lab['port'],dbname='aos_test_7c4f2f6b4aa8_ti4_test',user='aos_app',passfile=lab['passfile'])
results=[]
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 row=c.execute("SELECT prosrc,pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid='aos_capacity_publication_private.require_original_fact_boundary()'::regprocedure").fetchone()
 assert not re.search(r'\b(?:INSERT|UPDATE|DELETE|MERGE|TRUNCATE|EXECUTE|PERFORM)\b',re.sub(r"'(?:[^']|'')*'", "''",row[0]),re.I)
 before=c.execute("SELECT name,setting FROM pg_settings WHERE name IN ('jit','jit_above_cost','jit_inline_above_cost','jit_optimize_above_cost') ORDER BY name").fetchall()
 for mode in ['on','off','off','on']:
  c.execute('SET LOCAL jit='+mode)
  for iteration in range(6):
   t=time.perf_counter()
   c.execute('SELECT aos_capacity_publication_private.require_original_fact_boundary()')
   results.append(dict(jit=mode,iteration=iteration,seconds=time.perf_counter()-t,outcome='passed'))
 assert c.execute("SELECT prosrc FROM pg_proc WHERE oid='aos_capacity_publication_private.require_original_fact_boundary()'::regprocedure").fetchone()[0]==row[0]
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 after=c.execute("SELECT name,setting FROM pg_settings WHERE name IN ('jit','jit_above_cost','jit_inline_above_cost','jit_optimize_above_cost') ORDER BY name").fetchall();assert after==before;c.rollback()
data=dict(authority='AOS-001761',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),database=params['dbname'],cluster=lab['cluster'],routine_sha256=hashlib.sha256(row[0].encode()).hexdigest(),routine_owner=row[1],routine_security_definer=row[2],routine_search_path=row[3],before_settings=before,after_settings=after,settings_restored=True,samples=results,median_seconds={mode:statistics.median(x['seconds'] for x in results if x['jit']==mode) for mode in ['on','off']},formal_database_touched=False,source_issued=False,product_modified=False,execution_allowed=False,whole_source_timing_recovered=False,goal_complete=False)
with (OUT/'result.json').open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'samples':len(results),'median_seconds':data['median_seconds'],'settings_restored':True}))
