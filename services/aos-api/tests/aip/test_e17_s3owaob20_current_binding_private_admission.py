"""Current signed preview must not write CapabilityBinding through owner fallback."""

import pytest

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers import aip_bindings as routes


class ServiceReached(Exception):
    pass


class WriteSpy:
    def __getattr__(self, name):
        raise ServiceReached(name)


PRINCIPAL = Principal(subject="b20-test", org_id="org-org", project_id="dev-project")


@pytest.mark.parametrize(
    "invoke",
    [
        lambda service: routes.create_capability_binding(
            request=object(), idempotency_key="b20-create", principal=PRINCIPAL, service=service),
        lambda service: routes.evaluate_capability_binding(
            binding_id="b20-binding", request=object(), idempotency_key="b20-evaluate",
            principal=PRINCIPAL, service=service),
        lambda service: routes.activate_capability_binding(
            binding_id="b20-binding", request=object(), idempotency_key="b20-activate",
            principal=PRINCIPAL, service=service),
        lambda service: routes.suspend_capability_binding(
            binding_id="b20-binding", request=object(), idempotency_key="b20-suspend",
            principal=PRINCIPAL, service=service),
        lambda service: routes.revoke_capability_binding(
            binding_id="b20-binding", request=object(), idempotency_key="b20-revoke",
            principal=PRINCIPAL, service=service),
    ],
)
def test_current_preview_without_private_binding_identity_blocks_before_store(
    monkeypatch, invoke,
):
    monkeypatch.setenv("AOS_AIP_BINDING_REQUIRE_PRIVATE", "1")
    monkeypatch.setattr(routes, "_CAPABILITY_PRIVATE_CONFIGURED", False, raising=False)
    with pytest.raises(ApiError) as failure:
        invoke(WriteSpy())
    assert failure.value.status_code == 503
    assert failure.value.code == "AIP_BINDING_PRIVATE_CONFIGURATION_REQUIRED"


def test_current_preview_read_paths_remain_available(monkeypatch):
    monkeypatch.setenv("AOS_AIP_BINDING_REQUIRE_PRIVATE", "1")
    monkeypatch.setattr(routes, "_CAPABILITY_PRIVATE_CONFIGURED", False, raising=False)

    class ReadSpy:
        def list_bindings(self, scope, *, limit):
            assert scope.key == ("org-org", "dev-project") and limit == 10
            return []

        def get(self, scope, binding_id):
            assert scope.key == ("org-org", "dev-project") and binding_id == "b20-binding"
            return "real-read-result"

    service = ReadSpy()
    assert routes.list_capability_bindings(
        limit=10, principal=PRINCIPAL, service=service).count == 0
    assert routes.get_capability_binding(
        binding_id="b20-binding", principal=PRINCIPAL, service=service) == "real-read-result"


def test_non_preview_mode_keeps_existing_write_route(monkeypatch):
    monkeypatch.delenv("AOS_AIP_BINDING_REQUIRE_PRIVATE", raising=False)
    monkeypatch.setattr(routes, "_CAPABILITY_PRIVATE_CONFIGURED", False, raising=False)
    with pytest.raises(ServiceReached, match="create"):
        routes.create_capability_binding(
            request=object(), idempotency_key="b20-legacy", principal=PRINCIPAL,
            service=WriteSpy())


def test_current_preview_with_private_binding_service_reaches_write_route(monkeypatch):
    monkeypatch.setenv("AOS_AIP_BINDING_REQUIRE_PRIVATE", "1")
    monkeypatch.setattr(routes, "_CAPABILITY_PRIVATE_CONFIGURED", True)
    with pytest.raises(ServiceReached, match="create"):
        routes.create_capability_binding(
            request=object(), idempotency_key="b20-private", principal=PRINCIPAL,
            service=WriteSpy())
