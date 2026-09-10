import os
import pytest
from test_aip_budget_reservation_pg import database,runtime_connection
from aos_api import data_os_store as store
from aos_api.source_connection_config import SOURCE_CONNECTION_FIELDS
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


def test_registration_merges_current_database_configuration(database,monkeypatch):
    database.owner.execute('CREATE TABLE meta_source (LIKE public.meta_source INCLUDING ALL)')
    # Use the production token trigger, without its public history-writing trigger.
    database.owner.execute('CREATE TRIGGER source_configuration_token BEFORE INSERT OR UPDATE ON meta_source FOR EACH ROW EXECUTE FUNCTION public.source_configuration_token_ar2_010()')
    database.owner.execute('GRANT SELECT,INSERT,UPDATE ON meta_source TO aos_runtime')
    database.owner.execute('ALTER TABLE meta_source ENABLE ROW LEVEL SECURITY')
    database.owner.execute("CREATE POLICY scope ON meta_source TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
    monkeypatch.setattr(store,'connect',runtime_connection(database))
    monkeypatch.setattr(store,'ensure_data_os_schema',lambda:None)
    scope=TenantScope('org-org','dev-project')
    base={'id':'merge-source','type':'jdbc-mysql-ssh'}
    first=store.persist_source(scope,dict(base,password='synthetic-original',database='shop'),merge_existing=True)
    result=store.persist_source(scope,base,merge_existing=True)
    assert result['password']==first['password']
    rotated=store.persist_source(scope,dict(base,secretRef='vault://secrets/test',database='shop'),merge_existing=True,replace_fields=tuple(SOURCE_CONNECTION_FIELDS),expected_configuration_revision=first['configurationRevision'])
    assert rotated['configurationRevision'] != first['configurationRevision']
    for expected in (None, first['configurationRevision']):
        with pytest.raises(store.ApiError):
            store.persist_source(scope,dict(base,password='synthetic-stale'),merge_existing=True,replace_fields=tuple(SOURCE_CONNECTION_FIELDS),expected_configuration_revision=expected)
    public=store.load_source_metadata(scope)
    assert len(public)==1
    assert public[0]['configurationRevision']==rotated['configurationRevision']
    assert 'password' not in public[0] and 'secretRef' not in public[0]
    assert 'password' not in rotated
    assert store.persist_source(scope,base,merge_existing=True)['secretRef']==rotated['secretRef']
    with pytest.raises(store.ApiError):
        store.persist_source(scope,dict(base,type='file'),merge_existing=True)
    other=store.persist_source(TenantScope('dev-org','dev-project'),base,merge_existing=True)
    assert 'secretRef' not in other
