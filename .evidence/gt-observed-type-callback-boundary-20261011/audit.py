"""Bounded type catalog edges; no function execution or native grant."""
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
CALLBACKS=('typinput','typoutput','typreceive','typsend','typmodin','typmodout','typanalyze','typsubscript')

def inspect():
    lab=json.loads((ROOT/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
    source=ROOT/'.evidence/gt-expression-types-transient-catalog-20261011/r5'
    base=json.loads((source/'independent-readback.json').read_text());base['cluster']=lab['cluster']
    observed=set(json.loads((source/'observed-oids.json').read_text()))
    records=json.loads((source/'typed-records.json').read_text())
    seeds=sorted({v for row in records for v in row[2:] if v})
    zero=base
    container=json.loads(subprocess.check_output(['docker','--context','desktop-linux','inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Running":{{json .State.Running}}}',lab['name']],text=True))
    assert container=={'Id':lab['container_id'],'Image':lab['image'],'Running':True}
    queue=[];types=[];bindings=[];seen=set();function_edges=[];type_edges=[]
    with psycopg.connect(host='127.0.0.1',port=lab['port'],dbname=base['database'],user='aos_app',passfile=lab['passfile'],row_factory=dict_row) as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        c.execute('SET LOCAL search_path=pg_catalog,public')
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==base['cluster']==lab['cluster']
        assert c.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend'").fetchone()['n']==0
        for name,n in zero['table_counts'].items():
            assert n==0 and c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(*name.split('.')))).fetchone()['n']==0
        queue.extend(seeds)
        while queue:
            oid=queue.pop(0)
            if oid in seen:continue
            seen.add(oid);assert len(seen)<=256
            typ=c.execute('''SELECT t.oid,n.nspname AS schema,t.typname,t.typtype,t.typlen,t.typbyval,t.typalign,t.typstorage,t.typcategory,t.typelem::oid,t.typbasetype::oid,t.typrelid::oid,t.typcollation::oid,t.typnotnull FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE t.oid=%s''',(oid,)).fetchone();assert typ
            raw_callbacks=c.execute('SELECT '+','.join(k+'::oid AS '+k for k in CALLBACKS)+' FROM pg_type WHERE oid=%s',(oid,)).fetchone()
            typ['callbacks']=dict(raw_callbacks)
            for kind,target in raw_callbacks.items():
                if target:function_edges.append({'sourceTypeOid':oid,'kind':kind,'functionOid':target})
            for kind in ('typelem','typbasetype'):
                target=typ[kind]
                if target:type_edges.append({'source':oid,'kind':kind,'target':target});queue.append(target)
            if typ['typrelid']:
                attrs=c.execute('SELECT attnum,attname,atttypid::oid AS type_oid,atttypmod,attcollation::oid AS collation FROM pg_attribute WHERE attrelid=%s AND attnum>0 AND NOT attisdropped ORDER BY attnum',(typ['typrelid'],)).fetchall();typ['attributes']=attrs
                for attr in attrs:type_edges.append({'source':oid,'kind':'attribute:'+str(attr['attnum']),'target':attr['type_oid']});queue.append(attr['type_oid'])
            ranges=c.execute('SELECT rngtypid::oid,rngsubtype::oid,rngmultitypid::oid,rngcollation::oid,rngsubopc::oid,rngcanonical::oid,rngsubdiff::oid FROM pg_range WHERE rngtypid=%s OR rngmultitypid=%s',(oid,oid)).fetchall();typ['ranges']=ranges
            for rng in ranges:
                for kind in ('rngtypid','rngsubtype','rngmultitypid'):
                    target=rng[kind]
                    if target and target!=oid:type_edges.append({'source':oid,'kind':kind,'target':target});queue.append(target)
                for kind in ('rngcanonical','rngsubdiff'):
                    if rng[kind]:function_edges.append({'sourceTypeOid':oid,'kind':kind,'functionOid':rng[kind]})
            enum=c.execute('SELECT enumlabel,enumsortorder FROM pg_enum WHERE enumtypid=%s ORDER BY enumsortorder',(oid,)).fetchall()
            typ['enumCount']=len(enum);typ['enumMetadataHash']=hashlib.sha256(json.dumps(enum,default=str,sort_keys=True).encode()).hexdigest()
            constraints=c.execute('SELECT conname,contype,convalidated,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contypid=%s ORDER BY conname',(oid,)).fetchall();typ['domainConstraints']=constraints
            types.append(typ)
        callback_oids=sorted({x['functionOid'] for x in function_edges});assert len(callback_oids)<=1024
        functions=[]
        for oid in callback_oids:
            row=c.execute('''SELECT p.oid,p.oid::regprocedure::text AS signature,p.prosrc,p.probin,l.lanname AS language,p.proowner::regrole::text AS owner,p.prosecdef,p.proconfig,p.proacl::text AS acl,p.prosupport::oid AS support FROM pg_proc p JOIN pg_language l ON l.oid=p.prolang WHERE p.oid=%s''',(oid,)).fetchone();assert row
            row['sourceHash']=hashlib.sha256(row.pop('prosrc').encode()).hexdigest();functions.append(row)
        assert c.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']=='on';c.rollback()
    return {'outcome':'ACTUAL_EXPRESSION_TYPE_CALLBACK_CATALOG','database':base['database'],'cluster':base['cluster'],'seedTypes':seeds,'actualTypedRecordCount':len(records),'observerFunctionOids':sorted(observed),'callbacksAlsoObservedByPlanner':sorted(set(callback_oids)&observed),'callbacksNotRecordedByPlanner':sorted(set(callback_oids)-observed),'allCallbackExecutionEventsVerified':False,'types':sorted(types,key=lambda x:x['oid']),'typeEdges':type_edges,'typeCallbackEdges':function_edges,'typeCallbackFunctions':functions,'pseudoTypes':[{'oid':x['oid'],'name':x['typname']} for x in types if x['typtype']=='p'],'nineTablesZero':True,'databaseWrites':0,'businessFunctionsInvoked':0,'actualPolymorphicBindingsVerified':False,'implicitCastExpressionClosureVerified':False,'fullNativeClosure':False,'executionAuthorized':False}

if __name__=='__main__':
    target=R/'result.json';assert not target.exists(),'Existing result: reconcile only'
    first=inspect();second=inspect();assert first==second
    first['independentConnectionsExact']=True
    with target.open('x') as f:json.dump(first,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'actualSeedTypes':len(first['seedTypes']),'typedRecords':first['actualTypedRecordCount'],'callbacksNotRecordedByPlanner':len(first['callbacksNotRecordedByPlanner']),'types':len(first['types']),'callbackFunctions':len(first['typeCallbackFunctions']),'callbackEdges':len(first['typeCallbackEdges']),'pseudoTypes':first['pseudoTypes'],'databaseWrites':0}))
