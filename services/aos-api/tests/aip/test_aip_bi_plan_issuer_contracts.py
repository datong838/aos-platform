"""Exact command boundary for a future isolated BI Plan issuer."""

import pytest
from pydantic import ValidationError

from aos_api.aip_bi_plan_issuer_contracts import (
    BIIssuerPrepareCommand, BIIssuerRebindCommand,
)


def _prepare_payload(**changes):
    raw = {
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "installationId": "42785d78-5914-4a54-a078-e5d2c7f48481",
        "expectedETagVersion": 3, "idempotencyKey": "bi-prepare-1",
    }
    raw.update(changes)
    return raw


def _prepare(**changes):
    return BIIssuerPrepareCommand.model_validate(_prepare_payload(**changes))


def test_prepare_command_carries_exact_target_without_claimed_actor_or_secret_leak():
    command = _prepare()
    assert command.installation_id == "42785d78-5914-4a54-a078-e5d2c7f48481"
    assert command.expected_etag_version == 3
    assert "header.payload.signature" not in repr(command)
    assert "header.payload.signature" not in str(command.model_dump())
    with pytest.raises(ValidationError):
        _prepare(actor="admin")
    with pytest.raises(ValidationError) as error:
        _prepare(bearerToken="header.payload.signature.extra")
    assert "header.payload.signature.extra" not in str(error.value)


@pytest.mark.parametrize("changes", [
    {"schemaVersion": 2}, {"bearerToken": "dev"},
    {"orgId": " org-org"}, {"projectId": "dev project"},
    {"installationId": "not-uuid"},
    {"installationId": "42785D78-5914-4A54-A078-E5D2C7F48481"},
    {"expectedETagVersion": "3"}, {"expectedETagVersion": 0},
    {"idempotencyKey": ""}, {"idempotencyKey": " bad"},
])
def test_prepare_rejects_untrusted_or_inexact_input(changes):
    with pytest.raises(ValidationError):
        _prepare(**changes)


def test_rebind_requires_original_receipt_and_plan_version():
    raw = _prepare_payload()
    raw.update(planId="responsibility-plan-original", prepareIdempotencyKey="bi-prepare-1",
               expectedPlanVersion=2, idempotencyKey="bi-rebind-1")
    command = BIIssuerRebindCommand.model_validate(raw)
    assert (command.plan_id, command.prepare_key, command.expected_plan_version) == (
        "responsibility-plan-original", "bi-prepare-1", 2)
    with pytest.raises(ValidationError):
        BIIssuerRebindCommand.model_validate({**raw, "expectedPlanVersion": 0})
    with pytest.raises(ValidationError):
        BIIssuerRebindCommand.model_validate({**raw, "actor": "forged"})
