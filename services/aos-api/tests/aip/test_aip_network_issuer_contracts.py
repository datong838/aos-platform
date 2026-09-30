"""Strict no-effect contract for a future isolated network approval issuer."""

import pytest
from pydantic import ValidationError

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)


def _command(**overrides):
    raw = {
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": "proposal-1", "idempotencyKey": "decision-1",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "a" * 64,
                     "decision": "approved", "reason": "reviewed"},
    }
    raw.update(overrides)
    return NetworkIssuerDecisionCommand.model_validate(raw)


def test_decision_secret_and_exact_read_only_inquiry_contract():
    command = _command()
    expected = canonical_hash(command.decision.model_dump(mode="json", by_alias=True))
    assert command.request_hash == expected
    assert "header.payload.signature" not in repr(command)
    assert "header.payload.signature" not in command.model_dump_json()
    inquiry = command.inquiry()
    assert isinstance(inquiry, NetworkIssuerDecisionInquiry)
    assert inquiry.request_hash == expected
    assert inquiry.proposal_id == command.proposal_id
    assert inquiry.idempotency_key == command.idempotency_key
    assert "header.payload.signature" not in repr(inquiry)
    assert "header.payload.signature" not in inquiry.model_dump_json()


@pytest.mark.parametrize("override", [
    {"bearerToken": "dev"},
    {"bearerToken": "bad-token"},
    {"orgId": " org-org"},
    {"proposalId": ""},
    {"idempotencyKey": "x" * 121},
    {"actorId": "forged-checker"},
    {"roles": ["owner"]},
    {"decision": {"expectedProposalVersion": 1,
                  "expectedProposalHash": "short",
                  "decision": "approved"}},
])
def test_issuer_command_rejects_untrusted_shape(override):
    with pytest.raises(ValidationError):
        _command(**override)


def test_inquiry_cannot_carry_new_decision_or_mismatched_hash():
    command = _command()
    inquiry = command.inquiry()
    with pytest.raises(ValidationError):
        NetworkIssuerDecisionInquiry.model_validate({
            **inquiry.model_dump(mode="json", by_alias=True),
            "decision": {"decision": "approved"},
        })
    assert not inquiry.matches(_command(idempotencyKey="another-key"))
    assert not inquiry.model_copy(update={"request_hash": "b" * 64}).matches(command)
