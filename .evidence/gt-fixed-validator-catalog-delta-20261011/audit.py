"""Exact catalog delta; retained observations never grant execution."""
import hashlib
import json
import subprocess
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg import sql
R=Path(__file__).resolve().parent
ROOT=R.parents[1]
PRIOR=ROOT/'.evidence/gt-shared-parent-native-ending-20261011'
FIELDS=('aggtransfn','aggfinalfn','aggcombinefn','aggserialfn','aggdeserialfn','aggmtransfn','aggminvtransfn','aggmfinalfn')

def inspect():
    lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
    base=json.loads((PRIOR/'definer-boundary-1824/result.json').read_text())
    prior=json.loads((PRIOR/'planner-indirect-1798/result.json').read_text())
    zero=json.loads((PRIOR/'aggregate-group-source-1807/independent-readback.json').read_text())
    container=json.loads(subprocess.check_output(['docker','--context','desktop-linux','inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Running":{{json .State.Running}}}',lab['name']],text=True))
    assert container=={'Id':lab['container_id'],'Image':lab['image'],'Running':True}
    with psycopg.connect(host='127.0.0.1',port=lab['port'],dbname=base['database'],user='aos_app',passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        c.execute('SET LOCAL search_path=pg_catalog,public')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==base['cluster']==lab['cluster']==prior['cluster']
        assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n']==0
        for name,n in zero['table_counts'].items():
            assert n==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
        for f in base['functions']:
            row=c.execute('SELECT prosrc,proowner::regrole::text AS owner,proconfig,prosecdef FROM pg_proc WHERE oid=%s',(f['oid'],)).fetchone()
            assert hashlib.sha256(row['prosrc'].encode()).hexdigest()==f['source_sha256'] and row['owner']==f['owner'] and row['proconfig']==f['proconfig'] and row['prosecdef']==f['prosecdef']
        output=[];mapping={}
        for old in prior['functions']:
            oid=c.execute('SELECT to_regprocedure(%s)::oid AS oid',(old['signature'],)).fetchone()['oid'];mapping[old['oid']]=oid
            if oid is None:
                output.append({'oldOid':old['oid'],'signature':old['signature'],'missing':True});continue
            row=c.execute('''SELECT p.oid,p.oid::regprocedure::text AS signature,p.prosupport::oid AS support,p.prosrc,p.probin,l.lanname AS language,p.provolatile,p.proowner::regrole::text AS owner,p.prosecdef,p.proconfig FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=%s''',(oid,)).fetchone()
            row['source_sha256']=hashlib.sha256(row.pop('prosrc').encode()).hexdigest()
            differing=[k for k in ('signature','source_sha256','probin','language','provolatile','owner','prosecdef','proconfig') if row[k]!=old[k]]
            output.append({'oldOid':old['oid'],'currentOid':oid,'signature':old['signature'],'oidChanged':old['oid']!=oid,'differentMetadataFields':differing,'currentSourceHash':row['source_sha256']})
        edges=[]
        for old in prior['functions']:
            oid=mapping[old['oid']]
            if oid is None:continue
            outgoing={'prosupport':c.execute('SELECT prosupport::oid AS n FROM pg_proc WHERE oid=%s',(oid,)).fetchone()['n']}
            agg=c.execute('SELECT aggfnoid FROM pg_aggregate WHERE aggfnoid=%s',(oid,)).fetchone()
            if agg:
                for field in FIELDS:
                    outgoing[field]=c.execute(sql.SQL('SELECT {}::oid AS n FROM pg_aggregate WHERE aggfnoid=%s').format(sql.Identifier(field)),(oid,)).fetchone()['n']
                sort=c.execute('SELECT aggsortop::oid AS n FROM pg_aggregate WHERE aggfnoid=%s',(oid,)).fetchone()['n']
                if sort:outgoing['aggsortop.oprcode']=c.execute('SELECT oprcode::oid AS n FROM pg_operator WHERE oid=%s',(sort,)).fetchone()['n']
            for kind,target in outgoing.items():
                if target:edges.append({'source':oid,'target':target,'kind':kind})
        expected=[{'source':mapping[e['source']],'target':mapping[e['target']],'kind':e['kind']} for e in prior['edges']]
        order=lambda x:(x['source'] or -1,x['kind'],x['target'] or -1)
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on'
        c.rollback()
    return {'outcome':'CURRENT_FIXED_VALIDATOR_CATALOG_DELTA','cluster':base['cluster'],'oldObservedDatabase':prior['database'],'currentDatabase':base['database'],'oldCatalogFunctions':len(output),'functions':output,'currentEdges':sorted(edges,key=order),'mappedOldEdgesExact':sorted(edges,key=order)==sorted(expected,key=order),'currentFourSourcesMatch1824':True,'nineTablesZero':True,'databaseWrites':0,'businessFunctionCalls':0,'fullRuntimeClosure':False,'executionAuthorized':False}

if __name__=='__main__':
    target=R/'result.json';assert not target.exists(),'Existing result: reconcile only'
    first=inspect();second=inspect();assert first==second
    first['independentConnectionsExact']=True
    with target.open('x') as f:json.dump(first,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'functions':first['oldCatalogFunctions'],'oidChanges':sum(x.get('oidChanged',False) for x in first['functions']),'metadataChanges':sum(bool(x.get('differentMetadataFields')) for x in first['functions']),'missing':sum(x.get('missing',False) for x in first['functions']),'mappedOldEdgesExact':first['mappedOldEdgesExact'],'databaseWrites':0}))
