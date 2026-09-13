import pytest
from test_product_event_dispatch import principal,factory,SCOPE
from aos_api.ecommerce_growth_host_composition import (
    build_scoped_ecommerce_growth_registry,build_runtime_ecommerce_growth_registry,EVENT_CONTROL_OPERATION)
from aos_api.ecommerce_product_event_dispatch import EventControlRequestHostService


def test_control_is_only_added_to_scoped_registry():
    old=build_runtime_ecommerce_growth_registry()
    scoped=build_scoped_ecommerce_growth_registry(principal(),factory())
    assert scoped.operation_ids==(*old.operation_ids,EVENT_CONTROL_OPERATION)
    assert EVENT_CONTROL_OPERATION not in old.operation_ids


def test_control_dependencies_are_lazy_and_use_authenticated_identity(monkeypatch):
    from aos_api.pipeline_control_service import PipelineControlServiceFactory
    import aos_api.ecommerce_product_event_control_host_service as module
    calls=[];owner=object()
    monkeypatch.setattr(PipelineControlServiceFactory,'build_event_control_owner',lambda self,scope:calls.append(scope) or owner)
    class FakeService:
        def __init__(self,supplied,*,actor):
            assert supplied is owner and actor=='authenticated-user'
        def revalidate(self,**kwargs):return 'checked'
    monkeypatch.setattr(module,'ProductEventControlHostService',FakeService)
    service=EventControlRequestHostService(principal(),factory())
    assert calls==[]
    assert service.revalidate(scope=SCOPE,command={})=='checked'
    assert calls==[SCOPE]


def test_control_request_scope_cannot_drift():
    from aos_api.tenant_scope import TenantScope
    service=EventControlRequestHostService(principal(),factory())
    with pytest.raises(ValueError,match='scope'):service.execute(scope=TenantScope('dev-org','dev-project'),command={})


def test_control_never_uses_legacy_compatibility(monkeypatch):
    from types import SimpleNamespace
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter
    from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostBlocked
    router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal(),factory()),
        legacy_compat={EVENT_CONTROL_OPERATION:lambda **kwargs:pytest.fail('legacy control ran')})
    monkeypatch.setattr(router,'_issue',lambda *args:SimpleNamespace(handler_kind='legacy'))
    with pytest.raises(EcommerceGrowthHostBlocked):router.dispatch(scope=SCOPE,operation_id=EVENT_CONTROL_OPERATION,command={})
