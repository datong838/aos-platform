"""Target binding tests only; these do not prove signed approval or activation."""
import pytest

from aos_api.aip_runtime_guard_policy_store import materialize_policy
from aos_api.tenant_scope import TenantScope
from tests.aip.test_guard_policy_activation_pg import candidate


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_exact_target_rejects_payload_forgery_and_binds_tenant(kind):
    from aos_api.aip_guard_policy_activation import build_guard_activation_target, GuardActivationBlocked
    scope = TenantScope("org-org", "dev-project")
    item = candidate(kind)
    draft = materialize_policy(scope, "maker", item)
    active = type(item).model_validate({**item.model_dump(mode="json", by_alias=True),
                                       "revision": 2, "lifecycle": "active"})
    target = build_guard_activation_target(scope=scope, draft=draft, candidate=active, expected_version=1)
    assert target.source_content_hash == draft.content_hash
    for bad_source in (draft.model_copy(update={"content_hash": "a"*64}),
                       draft.model_copy(update={"owner": "forged-owner"})):
        with pytest.raises(GuardActivationBlocked):
            build_guard_activation_target(scope=scope, draft=bad_source, candidate=active, expected_version=1)
    with pytest.raises(GuardActivationBlocked):
        build_guard_activation_target(scope=TenantScope("dev-org", "dev-project"),
                                      draft=draft, candidate=active, expected_version=1)
    with pytest.raises(GuardActivationBlocked):
        build_guard_activation_target(scope=scope, draft=draft, candidate=active, expected_version=True)
    field = "allow_public_fallback" if kind == "egress" else "allow_direct_pii"
    with pytest.raises(GuardActivationBlocked):
        build_guard_activation_target(scope=scope, draft=draft,
                                      candidate=active.model_copy(update={field: True}), expected_version=1)
