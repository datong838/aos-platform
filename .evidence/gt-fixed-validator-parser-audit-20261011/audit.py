"""Read-only grammar-route audit, never a native closure or execution grant."""
import hashlib
import json
import subprocess
from pathlib import Path

import pglast
from pglast.parser import parse_sql_json
import psycopg
from psycopg.rows import dict_row
from psycopg import sql

R = Path(__file__).resolve().parent
ROOT = R.parents[1]
PRIOR = ROOT / '.evidence/gt-shared-parent-native-ending-20261011'

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def names(value):
    return tuple(n['String']['sval'] for n in value)

def counts(conn, tables):
    result = {}
    for name in tables:
        parts = name.split('.')
        assert len(parts) == 2 and parts[0] in {
            'aos_shared_parent_admission_private', 'aos_shared_parent_physical_private'}
        result[name] = conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(
            sql.Identifier(*parts))).fetchone()['n']
    return result

if __name__ == '__main__':
    assert not (R/'result.json').exists(), 'Existing audit: reconcile only'
    lab = json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
    baseline = json.loads((PRIOR/'definer-boundary-1824/result.json').read_text())
    previous = json.loads((PRIOR/'aggregate-group-source-1807/independent-readback.json').read_text())
    container = json.loads(subprocess.check_output(['docker','--context','desktop-linux',
        'inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Running":{{json .State.Running}}}',
        lab['name']], text=True))
    assert container == {'Id':lab['container_id'],'Image':lab['image'],'Running':True}
    rows = []
    with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',
        dbname=baseline['database'],passfile=lab['passfile'],row_factory=dict_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        identity = conn.execute('''SELECT system_identifier::text AS cluster,
            current_database() AS database,current_setting('server_version') AS version
            FROM pg_control_system()''').fetchone()
        assert identity['cluster'] == lab['cluster'] == baseline['cluster']
        assert identity['database'] == previous['database'] == baseline['database']
        assert conn.execute('''SELECT count(*) AS n FROM pg_stat_activity
            WHERE datname=current_database() AND pid<>pg_backend_pid()
            AND backend_type='client backend' ''').fetchone()['n'] == 0
        before = counts(conn, previous['table_counts'])
        assert before == previous['table_counts'] and not any(before.values())
        for seed in baseline['functions']:
            current = conn.execute('''SELECT p.oid,p.prosrc,p.proowner::regrole::text AS owner,
                p.proconfig,p.prosecdef,pg_get_functiondef(p.oid) AS definition
                FROM pg_proc p WHERE p.oid=%s''',(seed['oid'],)).fetchone()
            assert current and current['proconfig']==['search_path=pg_catalog'] and current['prosecdef']
            assert current['owner']==seed['owner']
            source_hash=hashlib.sha256(current['prosrc'].encode()).hexdigest()
            assert source_hash==seed['source_sha256']
            outcome={'oid':seed['oid'],'signature':seed['signature'],'sourceHash':source_hash,
                'sourceMatches1824':True,'proceduralParseSucceeded':False,
                'queries':[],'functionNameCandidates':[],'operatorNameCandidates':[],
                'castTypeNameCandidates':[],'semanticBindingVerified':False}
            try:
                tree=pglast.parse_plpgsql(current['definition'])
                outcome['proceduralParseSucceeded']=True
                (R/(str(seed['oid'])+'-procedural-tree.json')).write_text(
                    json.dumps(tree,ensure_ascii=False,indent=2)+'\n')
                functions=set();operators=set();casts=set()
                for node in walk(tree):
                    query=node.get('query')
                    if not isinstance(query,str):
                        continue
                    assert len(query.encode())<=65536
                    q={'originalQuery':query,'parseMode':node.get('parseMode'),
                        'sqlParseSucceeded':False,'transformation':'none'}
                    try:
                        try:
                            sql_tree=json.loads(parse_sql_json(query))
                        except pglast.Error:
                            q['transformation']='wrapped in SELECT for candidate expression syntax only'
                            sql_tree=json.loads(parse_sql_json('SELECT '+query))
                        q['sqlParseSucceeded']=True
                        for expression in walk(sql_tree):
                            if 'FuncCall' in expression:
                                functions.add(names(expression['FuncCall']['funcname']))
                            if 'A_Expr' in expression:
                                operators.add(names(expression['A_Expr']['name']))
                            if 'TypeCast' in expression:
                                casts.add(names(expression['TypeCast']['typeName']['names']))
                    except pglast.Error as exc:
                        q['error']=str(exc)[:240]
                    outcome['queries'].append(q)
                for name in sorted(functions):
                    assert len(name) in (1,2)
                    schema=name[0] if len(name)==2 else 'pg_catalog'
                    candidates=conn.execute('''SELECT p.oid,p.oid::regprocedure::text AS signature,
                        p.prosecdef,p.proowner::regrole::text AS owner,p.provolatile
                        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                        WHERE n.nspname=%s AND p.proname=%s ORDER BY p.oid''',
                        (schema,name[-1])).fetchall()
                    outcome['functionNameCandidates'].append({'name':name,'candidates':candidates,
                        'actualOverloadResolved':False})
                for name in sorted(operators):
                    candidates=conn.execute('''SELECT o.oid,o.oprleft::regtype::text AS left_type,
                        o.oprright::regtype::text AS right_type,
                        o.oprcode::regprocedure::text AS implementation
                        FROM pg_operator o JOIN pg_namespace n ON n.oid=o.oprnamespace
                        WHERE n.nspname='pg_catalog' AND o.oprname=%s ORDER BY o.oid''',
                        (name[-1],)).fetchall()
                    outcome['operatorNameCandidates'].append({'name':name,'candidates':candidates,
                        'actualOverloadResolved':False})
                outcome['castTypeNameCandidates']=[list(x) for x in sorted(casts)]
            except pglast.Error as exc:
                outcome['proceduralParseError']=str(exc)[:240]
            # Recheck actual source, not parser-generated or rewritten text.
            assert hashlib.sha256(conn.execute('SELECT prosrc FROM pg_proc WHERE oid=%s',
                (seed['oid'],)).fetchone()['prosrc'].encode()).hexdigest()==source_hash
            rows.append(outcome)
        assert counts(conn,previous['table_counts'])==before
        conn.rollback()
    report={'outcome':'FIXED_VALIDATOR_PARSER_ROUTE_VIABILITY_AUDIT','identity':identity,
        'parserVersion':pglast.__version__,'parserPostgresqlVersion':pglast.get_postgresql_version(),
        'grammarVersionMatchesNative':int(identity['version'].split('.')[0])==pglast.get_postgresql_version()[0],
        'functions':rows,'databaseWrites':0,'businessFunctionsInvoked':0,'sourceRequestsReplayed':0,
        'nineTablesZeroAndUnchanged':True,'wholeReachableClosureVerified':False,
        'nativeAdmissionRootVerified':False,'executionAuthorized':False}
    with (R/'result.json').open('x') as f:
        f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'outcome':report['outcome'],'grammarVersionMatchesNative':report['grammarVersionMatchesNative'],
        'functions':len(rows),'proceduralParsed':sum(x['proceduralParseSucceeded'] for x in rows),
        'wholeReachableClosureVerified':False,'databaseWrites':0}))
