"""Request wiring tests; fakes establish routing, not real release authority."""
import pytest
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.ecommerce_product_event_dispatch import EventAwareSchedulePutHostService

SCOPE = TenantScope('org-org', 'dev-project')
EVENT = {'policy': {'schemaVersion': 'aos.ecommerce.product-event-schedule-policy/v1'}}


def principal():
    return Principal(subject='authenticated-user', org_id=SCOPE.org_id,
                     project_id=SCOPE.project_id, roles=[], markings=[])


def factory():
    # No production dependencies are built by this routing-only fixture.
    return object.__new__(PipelineControlServiceFactory)


def test_timed_calls_remain_lazy(monkeypatch):
    from aos_api.ecommerce_growth_runtime_adapters import SchedulePutHostService
    monkeypatch.setattr(PipelineControlServiceFactory, 'build_event_owner',
                        lambda *_: pytest.fail('legacy request built event dependencies'))
    monkeypatch.setattr(SchedulePutHostService, 'revalidate', lambda self, **kw: 'legacy')
    service = EventAwareSchedulePutHostService(principal(), factory())
    assert service.revalidate(scope=SCOPE, command={}) == 'legacy'


@pytest.mark.parametrize('method', ['revalidate', 'execute', 'verify_receipt'])
def test_event_uses_authenticated_scope_and_actor(monkeypatch, method):
    import aos_api.ecommerce_product_event_host_service as module
    calls = []
    owner = object()
    monkeypatch.setattr(PipelineControlServiceFactory, 'build_event_owner',
                        lambda self, scope: calls.append(scope) or owner)
    class FakeService:
        def __init__(self, source_owner, *, actor):
            assert source_owner is owner
            assert actor == 'authenticated-user'
        def revalidate(self, **kwargs): return 'event'
        execute = verify_receipt = revalidate
    monkeypatch.setattr(module, 'ProductEventSchedulePutHostService', FakeService)
    service = EventAwareSchedulePutHostService(principal(), factory())
    assert getattr(service, method)(scope=SCOPE, command=EVENT) == 'event'
    assert calls == [SCOPE]


@pytest.mark.parametrize('method', ['revalidate', 'execute', 'verify_receipt'])
def test_scope_drift_rejected_before_build(method):
    service = EventAwareSchedulePutHostService(principal(), factory())
    with pytest.raises(ValueError, match='scope'):
        getattr(service, method)(scope=TenantScope('dev-org', 'dev-project'), command=EVENT)


@pytest.mark.parametrize('schema', [None, '', 'unknown', 1])
def test_unknown_schema_rejected(schema):
    service = EventAwareSchedulePutHostService(principal(), factory())
    with pytest.raises(ValueError, match='schema'):
        service.revalidate(scope=SCOPE, command={'policy': {'schemaVersion': schema}})


def test_factory_does_not_accept_arbitrary_callback():
    with pytest.raises(TypeError):
        EventAwareSchedulePutHostService(principal(), object())


def test_scoped_registry_preserves_other_eight_services():
    from aos_api.ecommerce_growth_host_composition import (
        build_scoped_ecommerce_growth_registry, build_runtime_ecommerce_growth_registry)
    baseline = build_runtime_ecommerce_growth_registry()
    scoped = build_scoped_ecommerce_growth_registry(principal(), factory())
    assert scoped.operation_ids == (*baseline.operation_ids, "ecommerce_growth_event_control")
    for operation in baseline.operation_ids:
        service = scoped._binding(operation).revalidate.__self__
        original = baseline._binding(operation).revalidate.__self__
        if operation == 'ecommerce_growth_schedule_put':
            assert type(service) is EventAwareSchedulePutHostService
        else:
            assert type(service) is type(original)


@pytest.mark.parametrize("operation", ["ecommerce_growth_schedule_put", "ecommerce_growth_event_control"])
def test_http_dependency_takes_identity_from_authentication(monkeypatch, operation):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from aos_api.auth import require_principal
    from aos_api.routers import ecommerce_growth_dispatch as route
    app = FastAPI()
    app.include_router(route.router)
    app.dependency_overrides[require_principal] = principal
    production_factory = factory()
    app.state.extension_runtime_control_plane = SimpleNamespace(pipeline_control_factory=production_factory)
    seen = []
    sentinel = object()
    def build(authenticated, supplied_factory):
        seen.append((authenticated.subject, supplied_factory))
        return sentinel
    class FakeCanonical:
        def __init__(self, registry): assert registry is sentinel
        def dispatch(self, *, scope, operation_id, command):
            assert scope == SCOPE
            assert operation_id == operation
            return {'routed': True}
    monkeypatch.setattr(route, 'build_scoped_ecommerce_growth_registry', build)
    monkeypatch.setattr(route, 'EcommerceGrowthCanonicalRouter', FakeCanonical)
    response = TestClient(app).post(f'/v1/ecommerce-growth/operations/{operation}', json=EVENT)
    assert response.status_code == 200
    assert seen == [('authenticated-user', production_factory)]
