"""BI-W9-05 tenant-bound disabled InstanceOverlay tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_instance_overlay import (
    BusinessInvestigationInstanceOverlay,
    evaluate_overlay_tenant,
    evaluate_instance_overlay,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/instance_overlay.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_overlay_is_exact_ref_tenant_bound_disabled_and_killed() -> None:
    overlay = BusinessInvestigationInstanceOverlay.model_validate(fixture_payload())
    receipt = evaluate_instance_overlay(overlay)
    tenant = evaluate_overlay_tenant(overlay, "org-org", "dev-project")
    assert tenant.status == "MATCHED_DISABLED"
    assert not tenant.activation_allowed and not tenant.external_effect
    assert not overlay.enabled and not overlay.activation_allowed
    assert overlay.installation_locked and overlay.kill_switch_engaged
    assert not overlay.session_policy.session_authorized
    assert not overlay.schedule_policy.enabled
    assert receipt.status == "passed" and "NO_SECRET_RESOLUTION" in receipt.non_claims


def test_cross_tenant_request_fails_closed_without_visibility_or_fallback() -> None:
    overlay = BusinessInvestigationInstanceOverlay.model_validate(fixture_payload())
    result = evaluate_overlay_tenant(overlay, "dev-org", "dev-project")
    assert result.status == "BLOCKED_TENANT_MISMATCH"
    assert not result.overlay_visible and not result.activation_allowed
    assert result.blocker == "TENANT_SCOPE_MISMATCH"


@pytest.mark.parametrize("value", ["plaintext", "vault://", "vault://a?x=y", "secret://a#b", "https://secret"])
def test_secret_ref_must_be_opaque_and_never_inline(value: str) -> None:
    payload = fixture_payload()
    payload["secretRef"] = value
    with pytest.raises(ValidationError, match="opaque SecretRef"):
        BusinessInvestigationInstanceOverlay.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("enabled",), True), (("activationAllowed",), True), (("installationLocked",), False),
        (("killSwitchEngaged",), False), (("sessionPolicy", "sessionAuthorized"), True),
        (("schedulePolicy", "enabled"), True), (("featureFlags", "browserObservation"), True),
        (("mappingExceptions", 0, "verificationRequired"), False),
        (("fulfillmentPolicy", "approvalRequired"), False),
    ],
)
def test_no_field_can_silently_activate_runtime(path: tuple, value: object) -> None:
    payload = fixture_payload()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        BusinessInvestigationInstanceOverlay.model_validate(payload)


def test_hash_and_exact_ref_types_fail_closed() -> None:
    drifted = fixture_payload()
    drifted["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="overlay content hash drifted"):
        evaluate_instance_overlay(BusinessInvestigationInstanceOverlay.model_validate(drifted))

    wrong = fixture_payload()
    wrong["accountRef"]["resourceType"] = "StoreRevision"
    with pytest.raises(ValueError, match="accountRef"):
        BusinessInvestigationInstanceOverlay.model_validate(wrong)


@pytest.mark.parametrize(
    "extra",
    [
        {"password": "secret"}, {"cookie": "secret"}, {"dsn": "db"}, {"pii": {}},
        {"pageBody": "body"}, {"url": "https://example.invalid"}, {"route": "/admin"},
        {"accountName": "real-account"}, {"storeName": "real-store"},
    ],
)
def test_overlay_rejects_secret_payload_instance_identity_and_page_content(extra: dict) -> None:
    payload = fixture_payload()
    payload.update(extra)
    with pytest.raises(ValidationError, match="Extra inputs"):
        BusinessInvestigationInstanceOverlay.model_validate(payload)
