"""Unit tests for StageTemplate source Bundle allowlist (W-E2)."""
from __future__ import annotations

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_stage_template_authority import (
    published_source_bundle_ref,
    resolve_stage_template_source,
)
from aos_api.tenant_scope import TenantScope


def test_published_solution_pack_resolves() -> None:
    scope = TenantScope("org-org", "dev-project")
    assert resolve_stage_template_source(scope, published_source_bundle_ref()) is True


def test_drifted_hash_fails_closed() -> None:
    scope = TenantScope("org-org", "dev-project")
    good = published_source_bundle_ref()
    bad = ExactRevisionRef(
        resource_type=good.resource_type,
        resource_id=good.resource_id,
        revision=good.revision,
        content_hash="0" * 64,
    )
    assert resolve_stage_template_source(scope, bad) is False
