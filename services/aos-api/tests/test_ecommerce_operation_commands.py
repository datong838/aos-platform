"""W3-12B1 strict read-only command readiness tests."""

from __future__ import annotations

from aos_api.ecommerce_operation_commands import EcommerceOperationCommands


def test_command_readiness_is_tenant_bound_canonical_and_fail_closed() -> None:
    envelope = EcommerceOperationCommands().read_readiness(
        org_id="org-org",
        project_id="dev-project",
    )

    assert envelope.tenant.model_dump(by_alias=True) == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }
    assert [item.command_id.value for item in envelope.commands] == [
        "classify",
        "createCase",
        "changeMembership",
        "manageSla",
        "automationKill",
        "refund",
    ]
    assert all(item.status.value == "blocked" for item in envelope.commands)
    assert all(item.blockers for item in envelope.commands)
    assert envelope.commands[-1].side_effect.value == "external"
    assert envelope.commands[-1].blockers[0].code == "EXTERNAL_ACTION_GATE_NOT_BOUND"


def test_command_readiness_does_not_expose_business_payload() -> None:
    payload = EcommerceOperationCommands().read_readiness(
        org_id="dev-org",
        project_id="dev-project",
    ).model_dump(mode="json", by_alias=True)
    text = str(payload).lower()

    assert "customer" not in text
    assert "payment" not in text
    assert "address" not in text
    assert "provider" not in text
    assert "amount" not in text
