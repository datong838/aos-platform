from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import importlib
import json
import sys
from pathlib import Path

import pytest


NOW = datetime(2026, 9, 11, 8, tzinfo=UTC)


def _module():
    root = Path(__file__).resolve().parents[4]
    package_root = root / "bundles/solutions/ecommerce-growth/backend"
    sys.path.insert(0, str(package_root))
    try:
        return importlib.import_module("ecommerce_growth.ecommerce_analyst_analysis_sources")
    finally:
        sys.path.remove(str(package_root))


def _hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _fixture():
    module = _module()
    payloads = [{"fact": "orders", "value": 3}, {"fact": "products", "value": 2}]
    refs = [
        {"resourceType": "Evidence", "resourceId": f"evidence-{index}", "revision": 1, "contentHash": _hash(payload)}
        for index, payload in enumerate(payloads, 1)
    ]
    bundle = {"resourceType": "EvidenceBundleRevision", "resourceId": "bundle-1", "revision": 2, "contentHash": "b" * 64}
    request = {
        "bundleRef": bundle,
        "grants": list(reversed([
            {"decisionId": f"disclosure-{index}", "request": {"evidenceRef": ref, "purpose": "source", "requestedLevel": "l3", "taskId": "task-1"}}
            for index, ref in enumerate(refs, 1)
        ])),
    }
    material = {
        "bundleRef": bundle,
        "cutoffAt": NOW.isoformat(),
        "marking": ["internal"],
        "items": [
            {"evidenceRef": ref, "disclosureRef": {"resourceType": "EvidenceDisclosureDecision", "resourceId": f"disclosure-{index}", "revision": 1, "contentHash": "d" * 64}, "expiresAt": (NOW + timedelta(minutes=5)).isoformat(), "payload": payload}
            for index, (ref, payload) in enumerate(zip(refs, payloads, strict=True), 1)
        ],
    }
    return module, request, material


def test_valid_host_material_is_canonical_and_preserves_bundle_order():
    module, request, material = _fixture()
    result = module.validate_analysis_bundle_material(request, material, now=NOW, max_bytes=10_000)
    assert result["bundleRef"] == request["bundleRef"]
    assert [item["payload"]["fact"] for item in result["items"]] == ["orders", "products"]


@pytest.mark.parametrize(
    "fault",
    [
        "bundle", "missing", "duplicate_grant", "task", "purpose", "level",
        "evidence_kind", "revision", "payload", "decision", "expired", "future", "marking", "oversize",
    ],
)
def test_incomplete_or_drifted_host_material_fails_closed(fault):
    module, request, material = _fixture()
    if fault == "bundle": material["bundleRef"] = {**material["bundleRef"], "resourceId": "other"}
    elif fault == "missing": material["items"].pop()
    elif fault == "duplicate_grant": request["grants"][1] = request["grants"][0]
    elif fault == "task": request["grants"][1]["request"]["taskId"] = "other"
    elif fault == "purpose": request["grants"][0]["request"]["purpose"] = "audit"
    elif fault == "level": request["grants"][0]["request"]["requestedLevel"] = "l2"
    elif fault == "evidence_kind": material["items"][0]["evidenceRef"]["resourceType"] = "DatasetRevision"
    elif fault == "revision": material["items"][0]["evidenceRef"]["revision"] = 2
    elif fault == "payload": material["items"][0]["payload"]["value"] = 999
    elif fault == "decision": material["items"][0]["disclosureRef"]["resourceId"] = "other"
    elif fault == "expired": material["items"][0]["expiresAt"] = NOW.isoformat()
    elif fault == "future": material["cutoffAt"] = (NOW + timedelta(seconds=1)).isoformat()
    elif fault == "marking": material["marking"] = []
    elif fault == "oversize": material["items"][0]["payload"]["padding"] = "x" * 10_000
    with pytest.raises(ValueError, match="INVALID_ANALYSIS_SOURCE_MATERIAL"):
        module.validate_analysis_bundle_material(request, material, now=NOW, max_bytes=500 if fault == "oversize" else 20_000)


def test_package_module_has_no_host_imports_or_io_symbols():
    path = Path(__file__).resolve().parents[4] / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_analysis_sources.py"
    source = path.read_text()
    assert "from aos_api" not in source
    assert "import aos_api" not in source
    assert "psycopg" not in source
    assert "db_connect" not in source
