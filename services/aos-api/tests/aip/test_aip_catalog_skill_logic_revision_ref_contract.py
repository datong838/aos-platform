from __future__ import annotations

from datetime import UTC, datetime

from aos_api.aip_agent_registry_contracts import (
    PublishSkillTemplateRequest,
    SkillTemplateRevision,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_contracts import ResourceRef


HASH = "a" * 64


def _ref(kind: str, asset_id: str = "asset") -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind, asset_id=asset_id, revision=1, content_hash=HASH
    )


def _evaluated_skill() -> SkillTemplateRevision:
    request = PublishSkillTemplateRequest(
        skill_id="ecommerce.skill.D03",
        revision=1,
        canonical_logic_id="ecommerce.logic.D03",
        lifecycle=TemplateLifecycle.EVALUATED,
        input_schema={},
        output_schema={},
        tool_allowlist=[],
        required_capabilities=["strategy.plan"],
        risk_level="medium",
        memory_policy_ref=_ref("MemoryPolicyRevision", "memory"),
        handoff_policy_ref=_ref("HandoffPolicyRevision", "handoff"),
        source_ref=ResourceRef(
            resource_type="SolutionPack",
            resource_id="solution.ecommerce.growth",
            revision="1.3.0",
            authority="bundle",
        ),
        source_license="internal",
        content_hash=HASH,
    )
    return SkillTemplateRevision(
        **request.model_dump(),
        created_by="pytest-contract",
        created_at=datetime(2026, 8, 18, tzinfo=UTC),
    )


def test_catalog_skill_json_always_includes_logic_revision_ref_key() -> None:
    """Workshop exact parsers must see the additive key; evaluated skills emit null."""
    dump = _evaluated_skill().model_dump(by_alias=True, mode="json")
    assert "logicRevisionRef" in dump
    assert dump["logicRevisionRef"] is None


def test_catalog_skill_json_keeps_logic_revision_ref_when_null_even_if_exclude_none_tempted() -> None:
    """Catalog responses must not drop null logicRevisionRef (w2 handoff contract)."""
    dump = _evaluated_skill().model_dump(by_alias=True, mode="json", exclude_none=False)
    assert "logicRevisionRef" in dump
    dropped = _evaluated_skill().model_dump(by_alias=True, mode="json", exclude_none=True)
    assert "logicRevisionRef" not in dropped
