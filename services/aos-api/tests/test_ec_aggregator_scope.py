from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from aos_api.ec_live_executor import _make_link_aggregator
from aos_api.tenant_scope import TenantScope
from aos_api.ecom_core_models import SyncScope
from test_ecom_consistency_store import store,obj,batch,ident,NOW
from test_ecom_core_models import VALID_PROPERTIES


def test_aggregator_counts_only_live_current_tenant_niushop_orders(store):
    for org,platform,shop,deleted in [('org-a','niushop','1',False),('other','niushop','1',False),
                                    ('org-a','synthetic','1',False),('org-a','niushop','other',False),
                                    ('org-a','niushop','1',True)]:
        external='deleted' if deleted else 'order'
        identity=ident(external,org=org).model_copy(update={'platform':platform,'shop_or_marketplace_id':shop})
        props=dict(VALID_PROPERTIES['Order'],memberId='member-1',createdAt=NOW.isoformat())
        record=obj('Order',external,identity=identity,properties=props,deleted=deleted)
        sync=SyncScope(org_id=org,workspace_id='workspace-a',platform=platform,shop_or_marketplace_id=shop,stream=external)
        store.apply_batch(batch(record,batch_scope=sync))
    aggregator=_make_link_aggregator(SimpleNamespace(ecom_consistency_store=store),TenantScope('org-a','workspace-a'))
    assert aggregator(frozenset({'member-1'}))=={'member-1':(1,NOW)}


def test_aggregator_failure_is_not_zero_orders():
    engine=Mock();engine.begin.side_effect=OSError('private connection details')
    aggregator=_make_link_aggregator(SimpleNamespace(ecom_consistency_store=SimpleNamespace(_engine=engine)),TenantScope('org-org','dev-project'))
    with pytest.raises(RuntimeError,match='^LINK_AGGREGATOR_READ_FAILED$'):
        aggregator(frozenset({'member'}))
    missing=_make_link_aggregator(SimpleNamespace(),TenantScope('org-org','dev-project'))
    with pytest.raises(RuntimeError,match='LINK_AGGREGATOR_STORE_REQUIRED'):
        missing(frozenset({'member'}))
