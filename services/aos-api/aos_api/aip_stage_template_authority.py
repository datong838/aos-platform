"""Minimal Bundle-backed StageTemplate sourceBundleRef allowlist (W-E2)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.tenant_scope import TenantScope

_BUNDLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "solution.ecommerce.growth": {
        "resourceType": "SolutionPack",
        "resourceId": "solution.ecommerce.growth",
        "revision": 1,
        "bundleVersion": "1.3.0",
        "profile": "ecommerce-standard",
        "stageTemplateHint": "ecommerce-standard-content-review",
    }
}


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def published_source_bundle_ref(bundle_id: str = "solution.ecommerce.growth") -> ExactRevisionRef:
    definition = _BUNDLE_DEFINITIONS[bundle_id]
    return ExactRevisionRef(
        resource_type="SolutionPack",
        resource_id=bundle_id,
        revision=int(definition["revision"]),
        content_hash=_canonical_json_hash(definition),
    )


def resolve_stage_template_source(scope: TenantScope, ref: ExactRevisionRef) -> bool:
    _ = scope
    if ref.resource_type != "SolutionPack":
        return False
    definition = _BUNDLE_DEFINITIONS.get(ref.resource_id)
    if definition is None:
        return False
    expected = published_source_bundle_ref(ref.resource_id)
    return ref.revision == expected.revision and ref.content_hash == expected.content_hash
