import pytest

from aos_api import action_template_registry
from aos_api.aip_policy_activation_action import (
    POLICY_ACTIVATION_ACTION_RISK,
    PolicyActivationActionTypeReserved,
    require_generic_action_type_mutable,
)
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers import actions


def _body(action_type_id):
    return actions.ActionTypeIn(id=action_type_id, name="test", objectType="WorkOrder")


def _principal():
    return Principal(subject="owner", org_id="org-org", project_id="dev-project")


@pytest.mark.parametrize("action_type_id", list(POLICY_ACTIVATION_ACTION_RISK))
def test_fixed_policy_action_ids_are_reserved(action_type_id):
    with pytest.raises(PolicyActivationActionTypeReserved):
        require_generic_action_type_mutable(action_type_id)


def test_similar_and_ordinary_ids_are_not_reserved():
    require_generic_action_type_mutable("aip_activate_network_policy_v2")
    require_generic_action_type_mutable("ordinary-work-order")


@pytest.mark.parametrize("endpoint", ["create", "update"])
def test_generic_editor_rejects_reserved_before_schema_or_db(monkeypatch, endpoint):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("generic action schema or DB must not be touched")
    monkeypatch.setattr(actions, "ensure_action_schema", unexpected)
    body = _body("aip_activate_network_policy")
    with pytest.raises(ApiError) as exc:
        if endpoint == "create":
            actions.create_action_type(body, _principal())
        else:
            actions.update_action_type(body.id, body, _principal())
    assert exc.value.code == "AIP_POLICY_ACTION_TYPE_RESERVED"
    assert exc.value.status_code == 403


@pytest.mark.parametrize("force", [False, True])
def test_plugin_seed_rejects_reserved_before_connect(monkeypatch, force):
    def unexpected():
        raise AssertionError("plugin seed must not connect")
    monkeypatch.setattr(action_template_registry, "connect", unexpected)
    with pytest.raises(PolicyActivationActionTypeReserved):
        action_template_registry.upsert_action_type({"id": "aip_activate_budget_policy"}, force=force)
