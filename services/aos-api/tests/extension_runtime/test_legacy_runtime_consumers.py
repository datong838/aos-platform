from types import SimpleNamespace
import pytest

from aos_api.tenant_scope import TenantScope
from aos_api.ontology_compose import active_ecommerce_installation
from aos_api.ontology_overlay import _lock_installation
from aos_api.errors import ApiError


@pytest.mark.parametrize('eligible',[False,None,1,'true'])
def test_ontology_cannot_read_or_write_through_legacy_runtime_installation(eligible):
    queries=[]
    class Conn:
        def execute(self,query,params):
            queries.append(query)
            return SimpleNamespace(fetchone=lambda:{'legacy_eligible':eligible})
    scope=TenantScope('org-org','dev-project')
    assert active_ecommerce_installation(Conn(),scope) is None
    with pytest.raises(ApiError):_lock_installation(Conn(),scope,'00000000-0000-0000-0000-000000000001')
    assert len(queries)==2
    assert all('asset_bundle_version' in query and 'legacy_eligible' in query for query in queries)
