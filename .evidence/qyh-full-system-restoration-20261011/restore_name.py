"""One exact metadata CAS on the loaded copy; preserve original databases."""
import json
import prepare_volume as P
from load_volume import TARGET

if __name__ == '__main__':
    assert not (P.R / 'restored-name-intent.json').exists(), 'Existing intent: reconcile only'
    assert json.loads((P.R / 'volume-load-terminal.json').read_text())['outcome'] == 'RETAINED647_VOLUME_LOADED_GREEN'
    before = P.M.fingerprint(TARGET)
    identity = P.native_identity(TARGET)
    assert identity['cluster'] == P.CLUSTER and identity['name'] == 'org-org' and identity['activeOtherConnections'] == 0
    timestamp = identity['nameUpdatedAt'].replace("'", "''")
    sql = "BEGIN ISOLATION LEVEL SERIALIZABLE; WITH changed AS (UPDATE ONLY public.meta_org SET name='栖月汇商贸有限公司',updated_at=clock_timestamp() WHERE id='org-org' AND name='org-org' AND updated_at='" + timestamp + "'::timestamptz RETURNING id) SELECT 1/count(*) FROM changed; COMMIT;"
    P.record('restored-name-intent.json', {'cluster': P.CLUSTER, 'database': P.M.DB, 'orgId': 'org-org', 'before': identity, 'sql': sql, 'originalDatabasesTouched': False})
    assert P.M.psql(TARGET, P.M.DB, sql) == '1'
    P.record('restored-name-write-terminal.json', {'exactlyOneRow': True})
    after = P.M.fingerprint(TARGET)
    assert len(before) == len(after) == 647
    changed = [a['table'] for a,b in zip(before,after) if a != b]
    assert changed == ['public.meta_org']
    assert [a for a in before if a['table']=='public.meta_org'][0]['rows'] == [a for a in after if a['table']=='public.meta_org'][0]['rows']
    identity = P.native_identity(TARGET)
    assert identity['name'] == '栖月汇商贸有限公司' and identity['disabledBindings'] is True
    P.record('restored-name-terminal.json', {'outcome': 'RETAINED_VOLUME_QIYUEHUI_NAME_GREEN', 'identity': identity, 'tableCount': 647, 'changedTables': changed, 'businessExecutionStarted': False})
    P.record('volume-fingerprint-after-name.json', after)
    print('RETAINED_VOLUME_QIYUEHUI_NAME_GREEN')
