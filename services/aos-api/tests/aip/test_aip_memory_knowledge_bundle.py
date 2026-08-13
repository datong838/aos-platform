from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    KnowledgeScope,
    KnowledgeSourceKind,
    KnowledgeSourceRef,
)
from aos_api.aip_memory_knowledge_bundle import (
    BUNDLE_SEED_ADAPTER_ID,
    VerticalPackSeedAdapter,
    vertical_pack_seed_adapter_definition,
)
from aos_api.aip_memory_pipeline_contracts import (
    KnowledgePipelineInputReceipt,
    KnowledgePipelineKind,
)
from aos_api.aip_memory_pipeline_service import AipMemoryPipelinePolicyBlocked
from aos_api.asset_registry import parse_knowledge_package_json

NOW = datetime(2026, 8, 13, 16, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def package(*, decision: str = "allowed"):
    return parse_knowledge_package_json(
        json.dumps(
            {
                "apiVersion": "aos.dev/knowledge-package/v1alpha1",
                "kind": "KnowledgePackage",
                "packageId": "vertical.ecommerce.beauty",
                "packageVersion": "1.0.0",
                "sourceInventory": [
                    {
                        "sourceId": "nmpa.inventory",
                        "sourceUri": "https://www.nmpa.gov.cn/example/list-i",
                        "observedAt": NOW.isoformat(),
                        "freshnessExpiresAt": (NOW + timedelta(days=30)).isoformat(),
                        "licenseId": "authorized-official-source",
                        "usagePolicy": "summary-and-citation",
                        "licenseDecision": decision,
                        "contentHash": "sha256:" + HASH_A,
                        "provider": "nmpa",
                        "providerVersion": "list-i-2026-08-13",
                    }
                ],
                "entries": [
                    {
                        "entryId": "ingredient.example",
                        "category": "ingredient",
                        "payloadPath": "content/knowledge/entries/ingredient.example.json",
                        "payloadHash": "sha256:" + HASH_B,
                        "sourceId": "nmpa.inventory",
                        "subject": {
                            "resourceType": "knowledge.subject",
                            "resourceId": "ingredient.example",
                            "revision": "1",
                            "authority": "vertical-pack",
                        },
                        "confidence": 0.92,
                        "markings": ["org:org-org", "project:dev-project"],
                        "applicability": ["vertical.ecommerce.beauty"],
                        "ownerRoles": ["shopping_advisor", "content_officer"],
                    }
                ],
                "rollback": {
                    "mode": "remove-projection-retain-canonical",
                    "receiptRequired": True,
                },
            }
        )
    )


def receipt(*, payload_hash: str = HASH_B, source_kind=KnowledgeSourceKind.AUTHORIZED_DOCUMENT):
    receipt_ref = ResourceRef(
        resource_type="aip.artifact_receipt",
        resource_id="receipt-entry-1",
        revision="1",
        authority="postgresql",
    )
    source = KnowledgeSourceRef(
        source_kind=source_kind,
        source_ref=receipt_ref,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="authorized-official-source",
        usage_policy="summary-and-citation",
        content_hash=payload_hash,
        provider="nmpa",
        provider_version="list-i-2026-08-13",
        applicability=["vertical.ecommerce.beauty"],
    )
    return KnowledgePipelineInputReceipt(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        receipt_ref=receipt_ref,
        artifact=ArtifactRef(
            artifact_type="knowledge-entry",
            artifact_id="ingredient.example",
            revision="1",
            content_hash=payload_hash,
        ),
        task_id="task-seed-1",
        run_id="run-seed-1",
        source=source,
    )


def test_adapter_maps_one_exact_entry_to_deterministic_semantic_draft() -> None:
    adapter = VerticalPackSeedAdapter(
        package(), entry_id="ingredient.example", source_revision=1
    )

    first = adapter.adapt(receipt(), pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)
    second = adapter.adapt(receipt(), pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)

    assert first == second
    assert len(first) == 1
    draft = first[0]
    assert draft.candidate_layer.value == "semantic"
    assert draft.knowledge_scope is KnowledgeScope.WORKSPACE
    assert draft.subject.resource_id == "ingredient.example"
    assert draft.confidence == 0.92
    assert draft.candidate_id.startswith("knowledge-candidate-")
    assert draft.source_id.startswith("knowledge-source-")


def test_definition_is_seed_only_and_contract_hash_is_caller_frozen() -> None:
    definition = vertical_pack_seed_adapter_definition(contract_hash=HASH_A)

    assert definition.adapter_id == BUNDLE_SEED_ADAPTER_ID
    assert definition.pipeline_kinds == [KnowledgePipelineKind.SEED_IMPORT]
    assert definition.receipt_types == ["aip.artifact_receipt"]
    assert definition.source_kinds == [KnowledgeSourceKind.AUTHORIZED_DOCUMENT]


@pytest.mark.parametrize(
    ("package_decision", "payload_hash", "kind", "reason"),
    [
        ("unknown", HASH_B, KnowledgePipelineKind.SEED_IMPORT, "license_unknown"),
        ("denied", HASH_B, KnowledgePipelineKind.SEED_IMPORT, "license_denied"),
        ("allowed", HASH_A, KnowledgePipelineKind.SEED_IMPORT, "payload_hash_mismatch"),
        ("allowed", HASH_B, KnowledgePipelineKind.NETWORK_LEARNING, "kind_not_allowed"),
    ],
)
def test_adapter_fails_closed_for_license_hash_and_kind(
    package_decision, payload_hash, kind, reason
) -> None:
    adapter = VerticalPackSeedAdapter(
        package(decision=package_decision),
        entry_id="ingredient.example",
        source_revision=1,
    )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match=reason):
        adapter.adapt(receipt(payload_hash=payload_hash), pipeline_kind=kind)


def test_adapter_rejects_public_scope_missing_entry_and_invalid_revision() -> None:
    with pytest.raises(ValueError, match="public package publication"):
        VerticalPackSeedAdapter(
            package(),
            entry_id="ingredient.example",
            source_revision=1,
            knowledge_scope=KnowledgeScope.PUBLIC_PACKAGE,
        )
    with pytest.raises(ValueError, match="resolve exactly once"):
        VerticalPackSeedAdapter(package(), entry_id="missing", source_revision=1)
    with pytest.raises(ValueError, match="must be positive"):
        VerticalPackSeedAdapter(package(), entry_id="ingredient.example", source_revision=0)


def test_adapter_rejects_source_kind_and_governance_drift() -> None:
    adapter = VerticalPackSeedAdapter(
        package(), entry_id="ingredient.example", source_revision=1
    )
    wrong_kind = receipt(source_kind=KnowledgeSourceKind.RESEARCH_ARTIFACT)
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="source_kind_invalid"):
        adapter.adapt(wrong_kind, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)

    drifted = receipt()
    drifted = drifted.model_copy(
        update={
            "source": drifted.source.model_copy(update={"provider_version": "drifted"})
        }
    )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="provider_version_drift"):
        adapter.adapt(drifted, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)

    wrong_artifact = receipt().model_copy(
        update={
            "artifact": receipt().artifact.model_copy(update={"artifact_id": "other.entry"})
        }
    )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="artifact_id_mismatch"):
        adapter.adapt(wrong_artifact, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)

    wrong_scope = receipt()
    wrong_scope = wrong_scope.model_copy(
        update={
            "source": wrong_scope.source.model_copy(
                update={"applicability": ["vertical.ecommerce.food"]}
            )
        }
    )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="applicability_drift"):
        adapter.adapt(wrong_scope, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT)
