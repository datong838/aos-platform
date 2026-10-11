"""Real isolated calibration; transaction rolls back all temporary objects."""
import hashlib,json,os,re
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
R=Path(__file__).resolve().parent
ROOT=R.parents[1]
PRIOR=ROOT/'.evidence/gt-shared-parent-native-ending-20261011'

def record(name,body):
    with (R/name).open('x') as f:json.dump(body,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())

def phase(name,body):
    with (R/'phases.jsonl').open('a') as f:f.write(json.dumps({'phase':name,**body})+'\n');f.flush();os.fsync(f.fileno())

if __name__=='__main__':
    assert not (R/'check-intent.json').exists(),'Already attempted: reconcile only'
    lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());base=json.loads((PRIOR/'definer-boundary-1824/result.json').read_text());zero=json.loads((PRIOR/'aggregate-group-source-1807/independent-readback.json').read_text());artifact=json.loads((R/'artifact-terminal.json').read_text())
    assert hashlib.sha256((R/'probe.so').read_bytes()).hexdigest()==artifact['librarySha256']
    record('check-intent.json',{'task':R.name,'database':base['database'],'cluster':lab['cluster'],'librarySha256':artifact['librarySha256'],'businessFunctionsWillBeInvoked':False,'temporaryDdlWillRollback':True})
    notices=[]
    def notice(d):
        match=re.fullmatch(r'TEST_FIXED_COLLECTOR_EXPRESSION_TYPES ([0-9]+(?: [0-9]+)+)',d.message_primary)
        if match:notices.append([int(x) for x in match[1].split()])
    with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=base['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
        c.add_notice_handler(notice);c.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');c.execute("SET LOCAL statement_timeout='15s'")
        assert c.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==base['cluster']==lab['cluster']
        assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n']==0
        for name,n in zero['table_counts'].items():assert n==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
        for f in base['functions']:
            x=c.execute('SELECT prosrc,proowner::regrole::text AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone()
            assert hashlib.sha256(x['prosrc'].encode()).hexdigest()==f['source_sha256'] and x['owner']==f['owner'] and x['proconfig']==f['proconfig'] and x['prosecdef']==f['prosecdef']
        array_fn=c.execute("SELECT 'pg_catalog.array_append(anycompatiblearray,anycompatible)'::regprocedure::oid AS oid").fetchone()['oid']
        c.execute('CREATE TEMP TABLE type_observer_scope_marker(n integer)')
        c.execute('SAVEPOINT old_symbol')
        try:
            c.execute(sql.SQL("CREATE FUNCTION pg_temp.type_calibration_old(boolean) RETURNS boolean AS {},'probe_type_expression_calibration' LANGUAGE C").format(sql.Literal(artifact['priorLibrary'])))
        except psycopg.Error as e:
            assert 'could not find function' in str(e) and 'probe_type_expression_calibration' in str(e);phase('old-capability-red',{'sqlstate':e.sqlstate,'symbolAbsent':True});c.execute('ROLLBACK TO SAVEPOINT old_symbol')
        else:raise AssertionError('Prior observer unexpectedly exports new calibration')
        c.execute(sql.SQL("CREATE FUNCTION pg_temp.type_calibration_new(boolean) RETURNS boolean AS {},'probe_type_expression_calibration' LANGUAGE C").format(sql.Literal(artifact['library'])))
        c.execute(sql.SQL("CREATE FUNCTION pg_temp.original_collector_negative(uuid,text,xid8,integer) RETURNS jsonb AS {},'probe_fixed_collector' LANGUAGE C").format(sql.Literal(artifact['library'])))
        c.execute('SAVEPOINT forced_error')
        try:c.execute('SELECT pg_temp.type_calibration_new(true)')
        except psycopg.Error as e:
            assert e.diag.message_primary=='TEST_TYPE_CALIBRATION_FORCED_ERROR';phase('forced-error',{'sqlstate':e.sqlstate,'expected':True});c.execute('ROLLBACK TO SAVEPOINT forced_error')
        else:raise AssertionError('Forced error missing')
        notices.clear();assert c.execute('SELECT pg_temp.type_calibration_new(false) AS ok').fetchone()['ok'];first=list(notices)
        assert any(x[1]==array_fn and x[2:]==[1007,1007,23] for x in first),first
        c.execute('SAVEPOINT identity_negative')
        try:c.execute("SELECT pg_temp.original_collector_negative('00000000-0000-0000-0000-000000000000', 'sha256:'||repeat('0',64), pg_current_xact_id(),pg_backend_pid())")
        except psycopg.Error as e:
            assert e.diag.message_primary=='TEST_FIXED_COLLECTOR_IDENTITY_REQUIRED';phase('original-identity-rejected',{'sqlstate':e.sqlstate,'expected':True});c.execute('ROLLBACK TO SAVEPOINT identity_negative')
        else:raise AssertionError('Original identity gate weakened')
        notices.clear();assert c.execute('SELECT pg_temp.type_calibration_new(false) AS ok').fetchone()['ok'];second=list(notices);assert first==second
        phase('typed-calibration-green',{'records':first,'arrayAppendFunctionOid':array_fn,'repeatedExact':True})
        c.rollback();assert c.execute("SELECT count(*) AS n FROM pg_proc WHERE proname IN ('type_calibration_old','type_calibration_new','original_collector_negative') AND pronamespace=pg_my_temp_schema()").fetchone()['n']==0;c.rollback()
    # Independent readback after the caller connection has closed.
    with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=base['database'],passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for name,n in zero['table_counts'].items():assert n==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
        assert c.execute("SELECT count(*) AS n FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE p.proname IN ('type_calibration_old','type_calibration_new','original_collector_negative') AND n.nspname LIKE 'pg_temp_%'").fetchone()['n']==0
        c.rollback()
    record('result.json',{'outcome':'ISOLATED_EXPRESSION_TYPE_CALIBRATION_GREEN','database':base['database'],'cluster':base['cluster'],'oldSymbolAbsentRed':True,'forcedErrorAndCleanupVerified':True,'originalCollectorIdentityRejected':True,'typedRecords':first,'arrayAppendFunctionOid':array_fn,'actualArrayAppendExpressionTypeBindings':{'returnType':1007,'inputTypes':[1007,23]},'repeatedCalibrationExact':True,'temporaryObjectsRolledBackAndAbsent':True,'independentNineTablesZero':True,'originalBusinessFunctionsInvoked':0,'fullSourceRunAccepted':False,'nativeRootAccepted':False,'executionAuthorized':False})
    print('real calibration passed; original collector rejected; temporary DDL rolled back')
