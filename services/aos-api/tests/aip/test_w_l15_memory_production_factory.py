"""W-L15 production memory factory: no None getters, fail-closed resolvers."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_memory_contracts import (
    ArtifactPiiStatus,
    KnowledgeSourceKind,
    KnowledgeSourceRef,
    LicensePolicyDecision,
)
from aos_api.aip_memory_production_factory import (
    build_memory_governance_service,
    build_memory_retrieval_service,
    build_memory_search_service,
    inspect_artifact_authority,
    resolve_license_authority,
    resolve_payload_authority,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect
from aos_api.routers import aip_memory_authority as memory_router
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
HASH = "a" * 64
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)


def test_production_router_getters_are_wired() -> None:
    assert memory_router.get_aip_memory_governance_service() is not None
    assert memory_router.get_aip_memory_retrieval_service() is not None
    assert memory_router.get_aip_memory_search_service() is not None
    assert isinstance(
        build_memory_governance_service(store=AipMemoryStore()), object
    )
    assert build_memory_retrieval_service() is not None
    assert build_memory_search_service() is not None


def test_missing_artifact_inspection_fails_closed() -> None:
    artifact = ArtifactRef(
        artifact_id=f"missing-{uuid.uuid4().hex[:8]}",
        artifact_type="knowledge",
        revision="1",
        content_hash=HASH,
    )
    with pytest.raises(LookupError, match="artifact_missing"):
        inspect_artifact_authority(SCOPE, artifact)


def test_artifact_without_pii_receipt_is_unknown() -> None:
    artifact_id = f"art-l15-{uuid.uuid4().hex[:10]}"
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_artifact
            (org_id,project_id,artifact_id,artifact_type,content_hash,created_by)
            VALUES(%s,%s,%s,'knowledge',%s,'test')""",
            (*SCOPE.key, artifact_id, HASH),
        )
        conn.commit()
    inspection = inspect_artifact_authority(
        SCOPE,
        ArtifactRef(
            artifact_id=artifact_id,
            artifact_type="knowledge",
            revision="1",
            content_hash=HASH,
        ),
    )
    assert inspection.pii_status is ArtifactPiiStatus.UNKNOWN


def test_license_unknown_without_matching_source_revision() -> None:
    source = KnowledgeSourceRef(
        source_kind=KnowledgeSourceKind.AUTHORIZED_DOCUMENT,
        source_uri="https://example.invalid/l15",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=7),
        license_id="lic-l15",
        usage_policy="internal_retrieval",
        content_hash="b" * 64,
        provider="aos",
        provider_version="1",
        applicability=["skill:content"],
    )
    assert resolve_license_authority(SCOPE, source) is LicensePolicyDecision.UNKNOWN


def test_payload_missing_blocks_resolver() -> None:
    artifact = ArtifactRef(
        artifact_id="payload-missing",
        artifact_type="knowledge",
        revision="1",
        content_hash="c" * 64,
    )
    with pytest.raises(LookupError, match="knowledge_payload_missing"):
        resolve_payload_authority(SCOPE, artifact)
