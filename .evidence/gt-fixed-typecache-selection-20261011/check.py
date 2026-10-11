import hashlib,json,os,re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
base=json.loads((R/'.evidence/gt-expression-types-transient-catalog-20261011/r5/independent-readback.json').read_text())
seed=json.loads((R/'.evidence/gt-observed-type-callback-boundary-20261011/result.json').read_text())
artifact=json.loads((B/'artifact-terminal.json').read_text());old=json.loads((R/'.evidence/gt-fixed-validator-expression-types-20261011/artifact-terminal.json').read_text())
assert not (B/'check-intent.json').exists(),'Existing attempt: reconcile only'
assert hashlib.sha256((B/'probe.so').read_bytes()).hexdigest()==artifact['librarySha256']
(B/'check-intent.json').write_text(json.dumps({'database':base['database'],'cluster':lab['cluster'],'librarySha256':artifact['librarySha256'],'fixedSeedCount':44,'temporaryDdlWillRollback':True,'callbacksWillNotBeExecuted':True},indent=2)+'\n')
notices=[];phases=[]
def notice(d):
 m=re.fullmatch(r'TEST_FIXED_TYPECACHE ([0-9]+(?: [0-9]+){10})',d.message_primary)
 if m:notices.append([int(i) for i in m[1].split()])
def open_connection():return psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=base['database'],passfile=lab['passfile'],row_factory=dict_row)
def zeros(c):
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 for name,count in base['table_counts'].items():assert count==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
 assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n']==0
with open_connection() as c:
 c.add_notice_handler(notice);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');c.execute("SET LOCAL statement_timeout='15s'");zeros(c)
 before=c.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
 for f in base['observed_functions']:
  row=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone();assert row and hashlib.sha256(row['prosrc'].encode()).hexdigest()==f['source_sha256']
 c.execute('CREATE TEMP TABLE typecache_scope_marker(n integer)')
 c.execute('SAVEPOINT old_symbol')
 try:c.execute(sql.SQL("CREATE FUNCTION pg_temp.typecache_prior(boolean) RETURNS boolean AS {},'probe_fixed_typecache' LANGUAGE C").format(sql.Literal(old['library'])))
 except psycopg.Error as e:
  assert 'could not find function' in str(e) and 'probe_fixed_typecache' in str(e);phases.append({'phase':'old_symbol_red','sqlstate':e.sqlstate});c.execute('ROLLBACK TO SAVEPOINT old_symbol')
 else:raise AssertionError('Old symbol unexpectedly present')
 c.execute(sql.SQL("CREATE FUNCTION pg_temp.typecache_fixed(boolean) RETURNS boolean AS {},'probe_fixed_typecache' LANGUAGE C").format(sql.Literal(artifact['library'])))
 c.execute('SAVEPOINT forced_error')
 try:c.execute('SELECT pg_temp.typecache_fixed(true)')
 except psycopg.Error as e:
  assert e.diag.message_primary=='TEST_TYPECACHE_FORCED_ERROR';phases.append({'phase':'forced_error','sqlstate':e.sqlstate});c.execute('ROLLBACK TO SAVEPOINT forced_error')
 else:raise AssertionError('Forced error missing')
 notices.clear();assert c.execute('SELECT pg_temp.typecache_fixed(false) AS ok').fetchone()['ok'];first=list(notices)
 assert len(first)==44 and {i[0] for i in first}=={i['oid'] for i in seed['types']}
 notices.clear();assert c.execute('SELECT pg_temp.typecache_fixed(false) AS ok').fetchone()['ok'];assert first==notices
 temp_schema=c.execute('SELECT nspname FROM pg_namespace WHERE oid=pg_my_temp_schema()').fetchone()['nspname']
 c.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(temp_schema)))
 c.execute('REVOKE ALL ON FUNCTION pg_temp.typecache_fixed(boolean) FROM PUBLIC');c.execute('GRANT EXECUTE ON FUNCTION pg_temp.typecache_fixed(boolean) TO aos_runtime')
 c.execute('SAVEPOINT wrong_identity');c.execute('SET LOCAL ROLE aos_runtime')
 try:c.execute('SELECT pg_temp.typecache_fixed(false)')
 except psycopg.Error as e:
  assert e.diag.message_primary=='TEST_TYPECACHE_IDENTITY_REQUIRED';phases.append({'phase':'runtime_identity_rejected','sqlstate':e.sqlstate});c.execute('ROLLBACK TO SAVEPOINT wrong_identity')
 else:raise AssertionError('Runtime accepted test helper')
 notices.clear();assert c.execute('SELECT pg_temp.typecache_fixed(false) AS ok').fetchone()['ok'];assert notices==first
 c.rollback()
 assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname IN ('typecache_prior','typecache_fixed') AND pronamespace=pg_my_temp_schema()").fetchone()['n']==0;c.rollback()
with open_connection() as c:
 c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');zeros(c)
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(before['xid'],)).fetchone()['status']=='aborted'
 assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname IN ('typecache_prior','typecache_fixed')").fetchone()['n']==0
 operators=sorted({v for row in first for v in row[5:8] if v});functions={v for row in first for v in row[8:] if v}
 ops=c.execute('SELECT oid,oid::regoperator::text AS signature,oprcode::oid AS function_oid FROM pg_operator WHERE oid=ANY(%s::oid[]) ORDER BY oid',(operators,)).fetchall();assert len(ops)==len(operators);functions.update(o['function_oid'] for o in ops)
 rows=c.execute('SELECT p.oid,p.oid::regprocedure::text AS signature,p.prosrc,p.probin,l.lanname AS language,p.proowner::regrole::text AS owner,p.prosecdef,p.proconfig,p.proacl::text AS acl,p.prosupport::oid AS support FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=ANY(%s::oid[]) ORDER BY p.oid',(sorted(functions),)).fetchall();assert len(rows)==len(functions)
 for row in rows:row['source_sha256']=hashlib.sha256(row.pop('prosrc').encode()).hexdigest()
 for f in base['observed_functions']:
  row=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone();assert row and hashlib.sha256(row['prosrc'].encode()).hexdigest()==f['source_sha256']
 c.rollback()
prior_observed=set(seed['observerFunctionOids']);prior_type_callbacks={f['oid'] for f in seed['typeCallbackFunctions']}
x={'outcome':'ACTUAL_FIXED_TYPECACHE_SELECTION_GREEN','database':base['database'],'cluster':lab['cluster'],'librarySha256':artifact['librarySha256'],'recordFields':['type_oid','btree_family','btree_input_type','hash_family','hash_input_type','equality_operator','less_operator','greater_operator','compare_function','hash_function','extended_hash_function'],'selections':first,'selectedOperators':ops,'selectedFunctions':rows,'selectedFunctionsNotInTypeCallbackColumns':sorted(functions-prior_type_callbacks),'selectedFunctionsNotInPlannerObserver':sorted(functions-prior_observed),'phases':phases,'threeNormalSelectionsExact':True,'caller':before,'callerXidAborted':True,'temporaryObjectsAbsent':True,'independentNineTablesZero':True,'originalRetainedFunctionHashesUnchanged':True,'temporaryDDLExecuted':True,'businessTableWrites':0,'selectedCallbacksExecuted':0,'mainSourceRerun':False,'originalSourceTypecacheFlagsProven':False,'completeNativeClosure':False,'formalBusinessAuthorized':False}
(B/'result.json').open('x').write(json.dumps(x,indent=2)+'\n');print(json.dumps({'selectedTypes':len(first),'selectedFunctions':len(rows),'notInTypeCallbackColumns':len(x['selectedFunctionsNotInTypeCallbackColumns']),'notInPlannerObserver':len(x['selectedFunctionsNotInPlannerObserver']),'callerXidAborted':True,'runtimeIdentityRejected':True}))
