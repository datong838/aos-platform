from __future__ import annotations

import uuid

import pytest

from aos_api.aip_agent_registry_contracts import (
    PublishCapabilityRevisionRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
)
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ResourceRef
from aos_api.db import connect

HASH_A = "a" * 64
HASH_B = "b" * 64


def asset(kind: str, identifier: str, content_hash: str = HASH_A):
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=identifier,
        revision=1,
        content_hash=content_hash,
    )


def request(capability_id: str, alias: str, *, content_hash: str = HASH_A):
    return PublishCapabilityRevisionRequest(
        capability_id=capability_id,
        revision=1,
        display_name="文案生成",
        lifecycle="published",
        aliases=[alias],
        input_schema_ref=asset("SchemaRevision", "CopyGenerationRequest"),
        output_schema_ref=asset("SchemaRevision", "CopyDraftRef"),
        risk_level="medium",
        required_data_refs=[],
        required_tool_refs=[],
        required_capability_refs=[],
        memory_policy_ref=asset("MemoryPolicy", "aip.memory.default"),
        handoff_policy_ref=asset("HandoffPolicy", "aip.handoff.default"),
        effect_review_schema_ref=asset("SchemaRevision", "EffectReviewRef"),
        license_policy_ref=asset("LicensePolicy", "aip.license.default"),
        readiness_policy_ref=asset("ReadinessPolicy", "aip.readiness.default"),
        readiness="blocked",
        readiness_reasons=["provider_unknown", "eval_pack_unavailable"],
        source_ref=ResourceRef(
            resource_type="SolutionPack",
            resource_id="solution.ecommerce.growth",
            revision="1.2.0",
            authority="asset-registry",
        ),
        source_license="internal",
        content_hash=content_hash,
    )


def test_capability_contract_rejects_alias_and_reference_drift():
    with pytest.raises(ValueError, match="cannot also be an alias"):
        request("copy.generate", "copy.generate")
    payload = request("copy.generate", "title.generate").model_dump()
    payload["required_capability_refs"] = [asset("ToolRevision", "wrong")]
    with pytest.raises(ValueError, match="CapabilityRevision"):
        PublishCapabilityRevisionRequest(**payload)


def test_capability_revision_is_exact_idempotent_and_alias_resolvable():
    suffix = uuid.uuid4().hex[:12]
    capability_id = f"test.copy.generate.{suffix}"
    alias = f"test.title.generate.{suffix}"
    registry = AipCapabilityRegistry()
    first = registry.publish(request(capability_id, alias), actor="pytest")
    second = registry.publish(request(capability_id, alias), actor="pytest")
    exact = registry.get(capability_id, 1)
    resolved = registry.resolve_alias(alias)
    assert first == second == exact == resolved
    assert exact.readiness.value == "blocked"
    assert exact.content_hash == HASH_A

    with pytest.raises(AipAgentRegistryConflict, match="different content"):
        registry.publish(
            request(capability_id, alias, content_hash=HASH_B), actor="pytest"
        )
    with pytest.raises(AipAgentRegistryNotFound, match="alias"):
        registry.resolve_alias(f"unknown.{suffix}")


def test_capability_alias_collision_fails_closed():
    suffix = uuid.uuid4().hex[:12]
    alias = f"test.shared.alias.{suffix}"
    registry = AipCapabilityRegistry()
    registry.publish(request(f"test.first.{suffix}", alias), actor="pytest")
    with pytest.raises(AipAgentRegistryConflict, match="another revision"):
        registry.publish(request(f"test.second.{suffix}", alias), actor="pytest")


def test_capability_tables_are_append_only():
    suffix = uuid.uuid4().hex[:12]
    capability_id = f"test.append.only.{suffix}"
    alias = f"test.append.alias.{suffix}"
    AipCapabilityRegistry().publish(request(capability_id, alias), actor="pytest")
    with connect() as conn:
        with pytest.raises(Exception, match="AIP6_REGISTRY_APPEND_ONLY"):
            conn.execute(
                "UPDATE aip_capability_revision SET display_name='changed' "
                "WHERE capability_id=%s AND revision=1",
                (capability_id,),
            )
        conn.rollback()
        with pytest.raises(Exception, match="AIP6_REGISTRY_APPEND_ONLY"):
            conn.execute("DELETE FROM aip_capability_alias WHERE alias=%s", (alias,))
        conn.rollback()


def test_runtime_role_can_only_read_capability_catalog():
    with connect() as conn:
        conn.execute("SET ROLE aos_runtime")
        assert conn.execute("SELECT count(*) FROM aip_capability_revision").fetchone()
        with pytest.raises(Exception, match="permission denied"):
            conn.execute(
                "INSERT INTO aip_capability_alias(alias,capability_id,capability_revision) "
                "VALUES ('runtime.forbidden','missing',1)"
            )
        conn.rollback()
