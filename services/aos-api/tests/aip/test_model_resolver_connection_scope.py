from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.tenant_scope import TenantScope

SCOPE=TenantScope('org-org','dev-project')
NOW=datetime.now(UTC)
REF=VersionedAssetRef(asset_type='ProviderInstanceRevision',asset_id='provider',revision=2,content_hash='a'*64)


@pytest.mark.parametrize('change', ['healthy','expired','hash','revision','unhealthy','missing'])
def test_health_stays_on_injected_connection_and_requires_exact_fresh_provider(monkeypatch,change):
    row={'status':'healthy','provider_ref':REF.model_dump(mode='json',by_alias=True),'expires_at':NOW+timedelta(minutes=1)}
    if change=='expired':row['expires_at']=NOW
    if change=='hash':row['provider_ref']['contentHash']='b'*64
    if change=='revision':row['provider_ref']['revision']=1
    if change=='unhealthy':row['status']='unhealthy'
    if change=='missing':row=None
    calls=[]
    @contextmanager
    def connect(scope):
        calls.append(scope)
        def execute(sql,params):
            assert params==(*SCOPE.key,REF.asset_id)
            return SimpleNamespace(fetchone=lambda:row)
        yield SimpleNamespace(execute=execute)
    def forbidden(*a,**k):raise AssertionError('default connection used')
    monkeypatch.setattr('aos_api.aip_model_runtime_resolver.db_connect',forbidden)
    resolver=AipModelRuntimeResolver(SimpleNamespace(_connect_factory=connect,_eval_authority_store=object()))
    assert resolver._health_is_fresh(SCOPE,REF,NOW) is (change=='healthy')
    assert calls==[SCOPE]


def test_gate_uses_injected_authority_with_exact_target_and_time():
    calls=[]
    authority=SimpleNamespace(require_exact_passed=lambda *a,**k:calls.append((a,k)))
    resolver=AipModelRuntimeResolver(SimpleNamespace(_eval_authority_store=authority))
    assert resolver._gate_passed(SCOPE,REF,REF,NOW)
    assert calls==[((SCOPE,REF),{'expected_target':REF,'now':NOW})]
