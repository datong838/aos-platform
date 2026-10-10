"""Native RED/repair/original runtime/rollback; never replay Source."""
import pathlib,json,psycopg
from psycopg.rows import dict_row
from aos_api import aip_provider_capacity_catalog_audit_profile as catalog
from aos_api import aip_provider_capacity_publication_transaction as transaction
from catalog_fixture_restore import original_family_restoration_statements
b=pathlib.Path(__file__).resolve().parent;r=b.parents[2]
lab=json.loads((r/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
prior=r/'.evidence/gt-shared-parent-atomic-admission-finalizer-20261010/receipt-catalog-native-1765-r1/result-r2.json'
db=json.loads(prior.read_text())['databases'][0]
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row)
snapshot="SELECT n.nspname,p.proname,p.proargtypes::text,p.prosrc,p.proacl::text,p.proowner::text,p.proconfig,p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='aos_capacity_publication_private' OR (n.nspname='public' AND (p.proname LIKE '%capacity%source%' OR p.proname='aos_capacity_evidence_epoch_lock')) ORDER BY n.nspname,p.proname,p.proargtypes::text"
with psycopg.connect(**params) as c:
    assert c.execute('SELECT system_identifier::text id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    before=c.execute(snapshot).fetchall()
    for statement in transaction.source_public_entry_statements(include_consumer=True):c.execute(statement)
    for statement in catalog.catalog_installation_statements(include_consumer=True):c.execute(statement)
    assert catalog.catalog_profile_is_installed(c)
    for statement in catalog.epoch.legacy_epoch_profile_restoration_statements():c.execute(statement)
    try:catalog.catalog_profile_is_installed(c)
    except ValueError as e:assert str(e)==catalog.ERROR
    else:raise AssertionError('mixed original family accepted')
    for statement in original_family_restoration_statements():c.execute(statement)
    assert catalog.catalog_profile_is_installed(c) is False
    c.execute('SET LOCAL ROLE aos_capacity_publication_owner')
    c.execute('SELECT '+catalog.epoch.INSTALLATION)
    c.rollback()
with psycopg.connect(**params) as c:
    c.execute('SET TRANSACTION READ ONLY');assert c.execute(snapshot).fetchall()==before
out=dict(database=db,mixed_family_red=True,fixed_original_family_recognized=True,original_private_audit_actual_owner_pass=True,native_exact_rollback_restored=True,source_replayed=False,execution_allowed=False,whole_receipt_pass=False,full_task_delivered=False)
(b/'result.json').open('x').write(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
