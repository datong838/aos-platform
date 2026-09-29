import pytest

from aos_api.aip_action_models import (
    CreateActionDraftRequest,
    CreateActionProposalRequest,
    ReviseActionDraftRequest,
)
from aos_api.aip_action_service import AipActionService
from aos_api.auth import Principal
from aos_api.errors import ApiError


@pytest.mark.parametrize("method,action_body", [
    ("create_proposal", CreateActionProposalRequest.model_validate({
        "actionTypeId": "aip_activate_network_policy", "purpose": "activate"
    })),
    ("create_draft", CreateActionDraftRequest.model_validate({
        "actionTypeId": "aip_activate_network_policy", "purpose": "activate"
    })),
    ("revise_draft", ReviseActionDraftRequest.model_validate({
        "actionTypeId": "aip_activate_network_policy", "purpose": "activate",
        "expectedRevision": 1, "expectedContentHash": "a" * 64,
    })),
])
def test_generic_action_producer_rejects_reserved_before_store(monkeypatch, method, action_body):
    class UnexpectedStore:
        def __getattr__(self, _name):
            raise AssertionError("generic store must not be read")
    def unexpected(*_args, **_kwargs):
        raise AssertionError("generic schema must not be seeded")
    monkeypatch.setattr("aos_api.aip_action_service.ensure_action_schema", unexpected)
    principal = Principal(subject="owner", org_id="org-org", project_id="dev-project")
    service = AipActionService(UnexpectedStore())
    with pytest.raises(ApiError) as exc:
        if method == "revise_draft":
            service.revise_draft(principal, "draft-1", "key-1", action_body)
        else:
            getattr(service, method)(principal, "key-1", action_body)
    assert exc.value.code == "AIP_POLICY_ACTION_PRODUCER_REQUIRED"
    assert exc.value.status_code == 403
