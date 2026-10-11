import importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('preserve_tools',R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
m.R=R;m.DB='aos_meta_head';TARGET='aos-qyh-history-restore-20261011'
baseline=json.loads((R.parent/'qyh-historical-full-restore-20261011'/'source-before.json').read_text())
expected=json.loads((R/'metadata-expectations.json').read_text())
def literal(value):return "'"+value.replace("'","''")+"'"
def check(version):
    current=m.fingerprint(TARGET);lookup={v['table']:v for v in current};checks=[]
    for row in baseline:
        table=row['table']
        if table=='public.alembic_version':continue
        additions=[v for v in expected if v['table']==table and v['step']<=version]
        if not additions:
            assert lookup.get(table)==row,table+' historical data drift'
            continue
        ids=','.join(literal(v['fields']['id']) for v in additions)
        query="SELECT json_build_object('table',"+literal(table)+",'rows',count(*),'hash',md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),''))) FROM ONLY "+table+' t WHERE id NOT IN ('+ids+')'
        historical=json.loads(m.psql(TARGET,m.DB,'BEGIN READ ONLY; '+query+'; COMMIT;'))
        assert historical==row,table+' existing rows altered'
        assert lookup[table]['rows']==row['rows']+len(additions),table+' unreviewed added rows'
        for item in additions:
            fields=item['fields'];pairs=','.join(literal(k)+','+k for k in fields)
            actual=json.loads(m.psql(TARGET,m.DB,'BEGIN READ ONLY; SELECT json_build_object('+pairs+') FROM '+table+' WHERE id='+literal(fields['id'])+'; COMMIT;'))
            assert actual==fields,table+' added metadata content differs'
            checks.append({'table':table,'id':fields['id'],'sourceStep':item['step'],'fieldsExact':True})
    return {'oldTablesChecked':len(baseline)-1,'historicalRowsUnchanged':True,'originalMigrationMetadataAdditions':checks,'currentTables':len(current)}
if __name__=='__main__':
    result=check(117);m.record('117-reviewed-preservation.json',result);print(json.dumps(result))
