from __future__ import annotations

import pytest
from pathlib import Path

from aos_api.o1_alias_migration import (
    AliasClassification,
    build_projection_payload,
    canonical_external_id,
    classify_alias,
    deterministic_hash,
)


def _authority() -> dict:
    return {
        "org_id": "org-org",
        "workspace_id": "dev-project",
        "platform": "niushop",
        "shop_or_marketplace_id": "1",
        "object_type": "Payment",
        "external_id": "niushop:1:42",
        "properties": {"payStatus": "paid", "amount": "10.00"},
        "derived_payload": {"pay_duration_min": "3.50"},
        "source_updated_at": "2026-08-09T12:00:00+00:00",
        "source_timezone": "+0800",
        "canonical_status": "paid",
        "raw_status": "1",
        "schema_version": 1,
    }


def test_canonical_external_id_is_platform_shop_and_source_pk() -> None:
    assert canonical_external_id("niushop", "1", "42") == "niushop:1:42"
    assert canonical_external_id("niushop", "1", "niushop:1:42") == "niushop:1:42"
    with pytest.raises(ValueError, match="scope"):
        canonical_external_id("", "1", "42")
    with pytest.raises(ValueError, match="another"):
        canonical_external_id("niushop", "1", "other:2:42")


def test_projection_payload_matches_single_projector_contract() -> None:
    payload = build_projection_payload(_authority())
    record = payload["record"]
    assert payload["entityKind"] == "object"
    assert record["identity"]["externalId"] == "niushop:1:42"
    assert record["properties"]["pay_duration_min"] == "3.50"
    assert "orgId" not in record["properties"]


def test_alias_classification_is_fail_closed() -> None:
    expected = build_projection_payload(_authority())["record"]["properties"]
    assert classify_alias(None, expected) is AliasClassification.COPY
    assert classify_alias(expected, expected) is AliasClassification.ALREADY_EQUAL
    assert classify_alias({"different": True}, expected) is AliasClassification.HASH_CONFLICT
    assert classify_alias(None, None) is AliasClassification.UNRESOLVED


def test_hash_is_key_order_stable_and_rejects_non_json_values() -> None:
    assert deterministic_hash({"b": 2, "a": 1}) == deterministic_hash({"a": 1, "b": 2})
    with pytest.raises(TypeError):
        deterministic_hash({"bad": object()})


def test_migration_versions_manifest_rows_by_run_id() -> None:
    migration = Path(__file__).parents[1] / "alembic/versions/o1d_002_alias_run_identity.py"
    text = migration.read_text(encoding="utf-8")
    assert "PRIMARY KEY (org_id,project_id,run_id,alias_entry_id)" in text
