"""BI-W9-02 disabled Niushop menu/database/object Profile tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_niushop_profile import (
    NIUSHOP_CANONICAL_TYPES,
    NIUSHOP_SEMANTIC_FAMILIES,
    NiushopProfile,
    evaluate_niushop_profile,
)


FIXTURE = Path(__file__).parent / "fixtures/business_investigation/niushop_profile.json"
HASH_B = f"sha256:{'b' * 64}"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_profile_covers_required_menu_database_and_object_semantics_without_access_claim() -> None:
    profile = NiushopProfile.model_validate(fixture_payload())
    receipt = evaluate_niushop_profile(profile)

    observed_families = {family for item in profile.menu_semantics for family in item.fact_families}
    observed_types = {value for item in profile.object_mappings for value in item.canonical_types}
    assert NIUSHOP_SEMANTIC_FAMILIES <= observed_families
    assert NIUSHOP_CANONICAL_TYPES <= observed_types
    assert all(item.requires_observation for item in profile.menu_semantics)
    assert all(item.requires_discovery and not item.physical_existence_verified for item in profile.database_domains)
    assert all(item.verification_required and not item.hydration_allowed for item in profile.object_mappings)
    assert not profile.enabled and not profile.source_access_authorized
    assert profile.installation_ref is None and profile.instance_overlay_ref is None
    assert receipt.status == "passed" and "NO_SOURCE_READ" in receipt.non_claims


def test_database_policy_is_bounded_read_only_and_has_no_mutation_escape() -> None:
    policy = NiushopProfile.model_validate(fixture_payload()).database_policy
    assert policy.connector_type == "jdbc-mysql-ssh"
    assert policy.transaction_read_only and policy.max_rows <= 1000 and policy.query_timeout_seconds <= 30
    assert set(policy.allowed_statements) == {"SHOW", "DESCRIBE", "EXPLAIN", "SELECT"}
    assert {"INSERT", "UPDATE", "DELETE", "DDL", "LOCK", "SET_GLOBAL", "FILE", "PROCEDURE"} <= set(policy.forbidden_statements)


def test_profile_hash_and_disabled_integrity_fail_closed() -> None:
    hash_drift = fixture_payload()
    hash_drift["contentHash"] = HASH_B
    with pytest.raises(ValueError, match="profile content hash drifted"):
        evaluate_niushop_profile(NiushopProfile.model_validate(hash_drift))

    for field in ("enabled", "sourceAccessAuthorized"):
        payload = fixture_payload()
        payload[field] = True
        with pytest.raises(ValidationError):
            NiushopProfile.model_validate(payload)

    physical = fixture_payload()
    physical["databaseDomains"][0]["physicalExistenceVerified"] = True
    with pytest.raises(ValidationError):
        NiushopProfile.model_validate(physical)

    hydration = fixture_payload()
    hydration["objectMappings"][0]["hydrationAllowed"] = True
    with pytest.raises(ValidationError):
        NiushopProfile.model_validate(hydration)


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://example.invalid"},
        {"route": "/admin/order"},
        {"selector": "#orders"},
        {"host": "db.invalid"},
        {"dsn": "mysql://secret"},
        {"secretRef": "secret"},
        {"account": "admin"},
        {"token": "secret"},
        {"cookie": "secret"},
        {"rawSample": {}},
    ],
)
def test_profile_rejects_runtime_locator_credentials_and_raw_samples(extra: dict) -> None:
    payload = fixture_payload()
    payload.update(extra)
    with pytest.raises(ValidationError, match="Extra inputs"):
        NiushopProfile.model_validate(payload)


def test_platform_and_mapping_contract_cannot_drift() -> None:
    platform = fixture_payload()
    platform["platform"] = "wechat_store"
    with pytest.raises(ValidationError):
        NiushopProfile.model_validate(platform)

    missing_family = fixture_payload()
    missing_family["menuSemantics"] = missing_family["menuSemantics"][:-1]
    with pytest.raises(ValidationError, match="required Niushop semantic families"):
        NiushopProfile.model_validate(missing_family)

    wrong_sql = fixture_payload()
    wrong_sql["databasePolicy"]["allowedStatements"].append("UPDATE")
    with pytest.raises(ValidationError, match="read-only SQL policy"):
        NiushopProfile.model_validate(wrong_sql)
