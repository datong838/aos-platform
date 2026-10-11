import hashlib,json,re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[1]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());base=json.loads((R/'.evidence/gt-expression-types-transient-catalog-20261011/r5/independent-readback.json').read_text());artifact=json.loads((B/'artifact-terminal.json').read_text());old=json.loads((R/'.evidence/gt-fixed-typecache-selection-20261011/artifact-terminal.json').read_text())
assert not (B/'check-intent.json').exists(),'Existing attempt: reconcile only'
assert hashlib.sha256((B/'probe.so').read_bytes()).hexdigest()==artifact['librarySha256']
(B/'check-intent.json').write_text(json.dumps({'database':base['database'],'cluster':lab['cluster'],'librarySha256':artifact['librarySha256'],'temporaryDDLWillRollback':True,'businessSourceWillNotRun':True},indent=2)+'\n')
notices=[];phases=[]
def notice(d):
 for kind,prefix,length in [('event','TEST_FMGR_EVENT ',2),('coverage','TEST_FMGR_COVERAGE ',8)]:
  if d.message_primary.startswith(prefix):
   values=d.message_primary[len(prefix):].split();assert len(values)==length and all(v.isdigit() for v in values);notices.append({'kind':kind,'values':[int(v) for v in values]})
def connection():return psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=base['database'],passfile=lab['passfile'],row_factory=dict_row)
def zeros(c):
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 for name,count in base['table_counts'].items():assert count==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
 assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n']==0
with connection() as c:
 c.add_notice_handler(notice);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');c.execute("SET LOCAL statement_timeout='15s'");zeros(c);caller=c.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone()
 for f in base['observed_functions']:
  row=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone();assert row and hashlib.sha256(row['prosrc'].encode()).hexdigest()==f['source_sha256']
 c.execute('CREATE TEMP TABLE fmgr_scope_marker(n integer)');c.execute('SAVEPOINT old_symbol')
 try:c.execute(sql.SQL("CREATE FUNCTION pg_temp.fmgr_prior(boolean) RETURNS boolean AS {},'probe_fmgr_calibration' LANGUAGE C").format(sql.Literal(old['library'])))
 except psycopg.Error as e:
  assert 'could not find function' in str(e) and 'probe_fmgr_calibration' in str(e);phases.append({'phase':'old_symbol_red','sqlstate':e.sqlstate});c.execute('ROLLBACK TO SAVEPOINT old_symbol')
 else:raise AssertionError('Old symbol unexpectedly present')
 c.execute(sql.SQL("CREATE FUNCTION pg_temp.fmgr_calibration(boolean) RETURNS boolean AS {},'probe_fmgr_calibration' LANGUAGE C").format(sql.Literal(artifact['library'])))
 c.execute("CREATE FUNCTION pg_temp.fmgr_positive(text) RETURNS integer LANGUAGE SQL VOLATILE SET search_path=pg_catalog AS 'SELECT pg_catalog.length($1)'")
 c.execute("CREATE FUNCTION pg_temp.fmgr_abort() RETURNS integer LANGUAGE SQL VOLATILE SET search_path=pg_catalog AS 'SELECT 1/0'")
 wrappers=c.execute("SELECT oid,proname,prosrc,proconfig,prosecdef,provolatile FROM pg_proc WHERE pronamespace=pg_my_temp_schema() AND proname IN ('fmgr_positive','fmgr_abort') ORDER BY proname").fetchall();assert len(wrappers)==2
 ids={x['proname']:x['oid'] for x in wrappers};assert all(x['proconfig']==['search_path=pg_catalog'] and not x['prosecdef'] and x['provolatile']=='v' for x in wrappers)
 assert {x['proname']:x['prosrc'] for x in wrappers}=={'fmgr_positive':'SELECT pg_catalog.length($1)','fmgr_abort':'SELECT 1/0'}
 length_oid=c.execute("SELECT 'pg_catalog.length(text)'::regprocedure::oid AS oid").fetchone()['oid']
 def normal():
  notices.clear();assert c.execute('SELECT pg_temp.fmgr_calibration(false) AS ok').fetchone()['ok'];record=list(notices)
  assert record==[{'kind':'event','values':[ids['fmgr_positive'],0]},{'kind':'event','values':[ids['fmgr_positive'],1]},{'kind':'coverage','values':[ids['fmgr_positive'],8,length_oid,8,2,2,2,8]}],record
  return record
 first=normal();c.execute('SAVEPOINT forced_abort');notices.clear()
 try:c.execute('SELECT pg_temp.fmgr_calibration(true)')
 except psycopg.Error as e:
  assert e.sqlstate=='22012';forced=list(notices);assert forced[-2:]==[{'kind':'event','values':[ids['fmgr_abort'],0]},{'kind':'event','values':[ids['fmgr_abort'],2]}],forced;phases.append({'phase':'actual_division_abort','sqlstate':e.sqlstate,'events':forced});c.execute('ROLLBACK TO SAVEPOINT forced_abort')
 else:raise AssertionError('Expected division error absent')
 second=normal();assert first==second
 temp=c.execute('SELECT nspname FROM pg_namespace WHERE oid=pg_my_temp_schema()').fetchone()['nspname'];c.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(temp)));c.execute('REVOKE ALL ON FUNCTION pg_temp.fmgr_calibration(boolean) FROM PUBLIC');c.execute('GRANT EXECUTE ON FUNCTION pg_temp.fmgr_calibration(boolean) TO aos_runtime')
 c.execute('SAVEPOINT runtime_identity');c.execute('SET LOCAL ROLE aos_runtime')
 try:c.execute('SELECT pg_temp.fmgr_calibration(false)')
 except psycopg.Error as e:
  assert e.diag.message_primary=='TEST_FMGR_IDENTITY_REQUIRED';phases.append({'phase':'runtime_identity_rejected','sqlstate':e.sqlstate});c.execute('ROLLBACK TO SAVEPOINT runtime_identity')
 else:raise AssertionError('Runtime accepted calibration')
 third=normal();assert third==first;c.rollback()
 assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE pronamespace=pg_my_temp_schema() AND proname IN ('fmgr_prior','fmgr_calibration','fmgr_positive','fmgr_abort')").fetchone()['n']==0;c.rollback()
with connection() as c:
 c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY');zeros(c)
 assert c.execute('SELECT pg_xact_status(%s::xid8) AS status',(caller['xid'],)).fetchone()['status']=='aborted'
 assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname IN ('fmgr_prior','fmgr_calibration','fmgr_positive','fmgr_abort')").fetchone()['n']==0
 for f in base['observed_functions']:
  row=c.execute('SELECT prosrc FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone();assert row and hashlib.sha256(row['prosrc'].encode()).hexdigest()==f['source_sha256']
 c.rollback()
result={'outcome':'FMGR_POSITIVE_AND_BYPASS_COVERAGE_CALIBRATION_GREEN','database':base['database'],'cluster':lab['cluster'],'librarySha256':artifact['librarySha256'],'normalRecords':first,'phases':phases,'wrappers':wrappers,'caller':caller,'threeNormalRecordsExact':True,'actualAbortStartAndAbortEvents':True,'hooksRestoredAfterErrorAndNormal':True,'builtinFmgrResult8WithoutEvents':True,'directCResult8WithoutEvents':True,'runtimeIdentityRejected':True,'callerXidAborted':True,'independentNineTablesZero':True,'temporaryObjectsAbsent':True,'originalPersistentFunctionHashesUnchanged':True,'temporaryDdlExecuted':True,'businessTableWrites':0,'originalSourceRerun':False,'completeNativeEventCoverage':False,'formalRootOrBusinessAccepted':False}
(B/'result.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['outcome','builtinFmgrResult8WithoutEvents','directCResult8WithoutEvents','actualAbortStartAndAbortEvents','hooksRestoredAfterErrorAndNormal','callerXidAborted']}))
