"""Production factory for AIP-5 memory governance / retrieval / search.

Resolvers only consult tenant-scoped authority tables. Missing or drifted
authority fails closed; this module never injects demo knowledge or static ALLOWED.
"""
from __future__ import annotations

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    ArtifactGovernanceInspection,
    ArtifactPiiStatus,
    KnowledgeSourceRef,
    LicensePolicyDecision,
)
from aos_api.aip_memory_governance import AipMemoryGovernanceService
from aos_api.aip_memory_retrieval import AipMemoryRetrieval, ResolvedKnowledgePayload
from aos_api.aip_memory_search import AipMemoryKnowledgeSearch
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

_ALLOW_USAGE = frozenset(
    {
        "internal_retrieval",
        "governed_retrieval",
        "workspace_retrieval",
        "organization_retrieval",
    }
)
_DENY_USAGE = frozenset({"denied", "revoked", "forbidden"})


def inspect_artifact_authority(
    scope: TenantScope, artifact: ArtifactRef, *, connect_factory=db_connect
) -> ArtifactGovernanceInspection:
    """Exact artifact must exist; PII remains unknown until an inspection receipt exists."""
    revision = artifact.revision
    if not revision or not artifact.content_hash:
        raise LookupError("artifact_ref_incomplete")
    with connect_factory(scope) as conn:
        row = conn.execute(
            """SELECT artifact_id, content_hash FROM aip_artifact
               WHERE org_id=%s AND project_id=%s AND artifact_id=%s
                 AND content_hash=%s""",
            (*scope.key, artifact.artifact_id, artifact.content_hash),
        ).fetchone()
        if row is None:
            raise LookupError("artifact_missing_or_drifted")
        inspection = conn.execute(
            """SELECT evidence_id, content_hash FROM aip_evidence
               WHERE org_id=%s AND project_id=%s
                 AND evidence_type='pii_inspection'
                 AND subject_ref @> %s::jsonb
               ORDER BY observed_at DESC LIMIT 1""",
            (
                *scope.key,
                AipMemoryStore._json(
                    {
                        "artifactId": artifact.artifact_id,
                        "contentHash": artifact.content_hash,
                    }
                ),
            ),
        ).fetchone()
    if inspection is None:
        return ArtifactGovernanceInspection(
            artifact=artifact,
            pii_status=ArtifactPiiStatus.UNKNOWN,
            inspection_ref=ResourceRef(
                resource_type="aip.pii_inspection",
                resource_id="pending",
                revision="0",
                authority="postgresql",
            ),
        )
    return ArtifactGovernanceInspection(
        artifact=artifact,
        pii_status=ArtifactPiiStatus.CLEAR,
        inspection_ref=ResourceRef(
            resource_type="aip.pii_inspection",
            resource_id=inspection["evidence_id"],
            revision="1",
            authority="postgresql",
        ),
    )


def resolve_license_authority(
    scope: TenantScope, source: KnowledgeSourceRef, *, connect_factory=db_connect
) -> LicensePolicyDecision:
    """License is authoritative only when source revision hash matches tenant store."""
    with connect_factory(scope) as conn:
        row = conn.execute(
            """SELECT license_id, usage_policy, content_hash
               FROM aip_memory_source_revision
               WHERE org_id=%s AND project_id=%s AND content_hash=%s
               ORDER BY revision DESC LIMIT 1""",
            (*scope.key, source.content_hash),
        ).fetchone()
    if row is None:
        return LicensePolicyDecision.UNKNOWN
    if row["license_id"] != source.license_id or row["usage_policy"] != source.usage_policy:
        return LicensePolicyDecision.UNKNOWN
    policy = str(row["usage_policy"]).strip().lower()
    if policy in _DENY_USAGE:
        return LicensePolicyDecision.DENIED
    if policy in _ALLOW_USAGE:
        return LicensePolicyDecision.ALLOWED
    return LicensePolicyDecision.UNKNOWN


def resolve_payload_authority(
    scope: TenantScope, artifact: ArtifactRef, *, connect_factory=db_connect
) -> ResolvedKnowledgePayload:
    """Body content must come from tenant evidence; never synthesize text."""
    if not artifact.content_hash:
        raise LookupError("payload_hash_missing")
    with connect_factory(scope) as conn:
        row = conn.execute(
            """SELECT evidence_id, content_hash, payload FROM aip_evidence
               WHERE org_id=%s AND project_id=%s
                 AND evidence_type='knowledge_payload'
                 AND content_hash=%s
               ORDER BY observed_at DESC LIMIT 1""",
            (*scope.key, artifact.content_hash),
        ).fetchone()
    if row is None:
        raise LookupError("knowledge_payload_missing")
    payload = row["payload"] if isinstance(row["payload"], dict) else {}
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise LookupError("knowledge_payload_body_missing")
    token_count = max(1, len(content.strip().split()))
    return ResolvedKnowledgePayload(
        artifact=artifact, content=content.strip(), token_count=token_count
    )


def build_memory_governance_service(
    *, store: AipMemoryStore | None = None, connect_factory=db_connect
) -> AipMemoryGovernanceService:
    return AipMemoryGovernanceService(
        artifact_inspector=lambda scope, artifact: inspect_artifact_authority(
            scope, artifact, connect_factory=connect_factory
        ),
        license_resolver=lambda scope, source: resolve_license_authority(
            scope, source, connect_factory=connect_factory
        ),
        store=store or AipMemoryStore(connect_factory),
        connect_factory=connect_factory,
    )


def build_memory_retrieval_service(*, connect_factory=db_connect) -> AipMemoryRetrieval:
    return AipMemoryRetrieval(
        payload_resolver=lambda scope, artifact: resolve_payload_authority(
            scope, artifact, connect_factory=connect_factory
        ),
        connect_factory=connect_factory,
    )


def build_memory_search_service(*, connect_factory=db_connect) -> AipMemoryKnowledgeSearch:
    return AipMemoryKnowledgeSearch(
        payload_resolver=lambda scope, artifact: resolve_payload_authority(
            scope, artifact, connect_factory=connect_factory
        ),
        connect_factory=connect_factory,
    )
