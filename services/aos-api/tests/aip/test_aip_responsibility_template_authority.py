"""Unit tests for Bundle allowlist ResponsibilityTemplate authority (W-E1)."""
from __future__ import annotations

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_template_authority import (
    published_template_ref,
    resolve_responsibility_template,
)
from aos_api.tenant_scope import TenantScope


def test_published_ecommerce_standard_resolves() -> None:
    scope = TenantScope("org-org", "dev-project")
    ref = published_template_ref("ecommerce-standard")
    assert resolve_responsibility_template(scope, ref) is True


def test_drifted_hash_fails_closed() -> None:
    scope = TenantScope("org-org", "dev-project")
    good = published_template_ref("ecommerce-standard")
    bad = ExactRevisionRef(
        resource_type=good.resource_type,
        resource_id=good.resource_id,
        revision=good.revision,
        content_hash="0" * 64,
    )
    assert resolve_responsibility_template(scope, bad) is False


def test_unknown_template_fails_closed() -> None:
    scope = TenantScope("org-org", "dev-project")
    ref = ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id="missing-template",
        revision=1,
        content_hash="a" * 64,
    )
    assert resolve_responsibility_template(scope, ref) is False
