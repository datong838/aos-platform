"""Minimal Bundle-backed ResponsibilityTemplateRevision allowlist authority.

W-E1: until signed VerticalPack template installation lock exists, only exact
allowlisted template refs resolve. This is NOT a second lifecycle DB authority —
it is an additive fail-closed allowlist keyed by Bundle-declared template ids.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope

# Stable L0 template definitions published with solution.ecommerce.growth.
# contentHash = sha256 of canonical JSON (sorted keys, no whitespace).
_TEMPLATE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "ecommerce-standard": {
        "resourceType": "ResponsibilityTemplateRevision",
        "resourceId": "ecommerce-standard",
        "revision": 1,
        "profile": "ecommerce-standard",
        "sourceBundle": {
            "resourceType": "SolutionPack",
            "resourceId": "solution.ecommerce.growth",
            "revision": "1.3.0",
        },
        "slots": [
            {
                "slotId": "content.review",
                "responsibilityType": "independent_review",
                "requiredCapabilityIds": ["content.review"],
            }
        ],
    }
}


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def published_template_ref(template_id: str) -> ExactRevisionRef:
    definition = _TEMPLATE_DEFINITIONS[template_id]
    return ExactRevisionRef(
        resource_type="ResponsibilityTemplateRevision",
        resource_id=template_id,
        revision=int(definition["revision"]),
        content_hash=_canonical_json_hash(definition),
    )


def resolve_responsibility_template(scope: TenantScope, ref: ExactRevisionRef) -> bool:
    """Return True only for exact allowlisted Bundle template refs."""
    _ = scope  # tenant isolation enforced by plan store; templates are shared definitions
    if ref.resource_type != "ResponsibilityTemplateRevision":
        return False
    definition = _TEMPLATE_DEFINITIONS.get(ref.resource_id)
    if definition is None:
        return False
    expected = published_template_ref(ref.resource_id)
    return (
        ref.revision == expected.revision
        and ref.content_hash == expected.content_hash
    )


def bundle_path_hint() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "bundles/releases/ecommerce/solution.ecommerce.growth/1.3.0"
    )
