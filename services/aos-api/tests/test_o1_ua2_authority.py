from __future__ import annotations

import pytest

from aos_api.ontology_operational_authority import (
    ActionPolicy,
    EvidencePayload,
    KnowledgePayload,
    composed_policy_etag,
    compose_action_policy,
    validate_payload,
)


def test_knowledge_requires_typed_subject_and_source() -> None:
    payload = KnowledgePayload.model_validate({
        "title": "Payment 结算口径",
        "body": "以权威 Payment 对象为准",
        "level": "L3",
        "confidence": 0.9,
        "subject": {"subjectType": "object_type", "subjectId": "Payment"},
        "sources": [{"sourceType": "document", "sourceRef": "doc:payment", "revision": "sha256:" + "a" * 64}],
        "visibility": "organization_private",
    })
    assert payload.subject.subject_type == "object_type"
    with pytest.raises(ValueError):
        KnowledgePayload.model_validate({"title": "x", "body": "y", "sources": []})


def test_sensitive_evidence_requires_retention_policy() -> None:
    with pytest.raises(ValueError, match="retention"):
        EvidencePayload.model_validate({
            "subjectRef": {"kind": "object", "id": "Payment/niushop:1:1"},
            "conclusion": "verified",
            "contentHash": "sha256:" + "b" * 64,
            "sensitive": True,
        })


def test_action_overlay_can_only_tighten() -> None:
    base = ActionPolicy(risk_level="medium", requires_approval=True, capabilities={"order.read", "order.write"})
    tightened = compose_action_policy(base, ActionPolicy(risk_level="high", requires_approval=True, capabilities={"order.read"}))
    assert tightened.risk_level == "high"
    assert composed_policy_etag(base, tightened) != composed_policy_etag(
        base, ActionPolicy(risk_level="high", requires_approval=True, capabilities=set())
    )
    with pytest.raises(ValueError, match="lower"):
        compose_action_policy(base, ActionPolicy(risk_level="low", requires_approval=True, capabilities={"order.read"}))
    with pytest.raises(ValueError, match="approval"):
        compose_action_policy(base, ActionPolicy(risk_level="high", requires_approval=False, capabilities={"order.read"}))
    with pytest.raises(ValueError, match="capabilities"):
        compose_action_policy(base, ActionPolicy(risk_level="high", requires_approval=True, capabilities={"refund.execute"}))


def test_unknown_record_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="record kind"):
        validate_payload("anything", {})


def test_canonical_hash_rejects_non_json_values() -> None:
    from aos_api.ontology_operational_authority import canonical_hash

    with pytest.raises(TypeError):
        canonical_hash({"notJson": object()})
