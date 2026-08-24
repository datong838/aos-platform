from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "w3_10_common_orchestration_gate.py"
SPEC = importlib.util.spec_from_file_location("w3_10_common_orchestration_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def manifest() -> dict:
    release_id = "w3-candidate-test"
    cutoff = "2026-08-25T02:00:00+08:00"
    sha = "a" * 40
    common = {
        "releaseId": release_id,
        "cutoff": cutoff,
        "status": "green",
        "evidenceKind": "local_candidate_runtime",
        "evidenceRefs": ["evidence:w3"],
    }
    return {
        "schema": gate.SCHEMA,
        "release": {
            "id": release_id,
            "gitCommit": sha,
            "schemaHash": "sha256:schema",
            "openapiHash": "sha256:openapi",
            "webBuildHash": "sha256:web",
            "migrationHead": "w3_017",
            "cutoff": cutoff,
        },
        "receiptRefs": [
            {"taskId": task, "status": "green", "commit": sha, "isAncestor": True, "evidenceRef": f"delivery:{task}"}
            for task in gate.TASKS
        ],
        "axes": {
            "contract": {**common, "schemaHash": "sha256:schema", "openapiHash": "sha256:openapi", "exactRefs": True, "errorsVisible": True},
            "store": {**common, "tenant": gate.TENANT, "migrationHead": "w3_017", "rls": True, "cas": True, "idempotency": True, "restartReadback": True, "liveMigrationApplied": False},
            "apiSdk": {**common, "tenant": gate.TENANT, "openapiHash": "sha256:openapi", "strictSdk": True, "canonicalOperations": True, "failClosedErrors": True, "formalHttp": True},
            "web": {**common, "tenant": gate.TENANT, "webBuildHash": "sha256:web", "publicPackageUnique": True, "typedIntents": True, "nineStates": True, "contributionLineage": True},
            "browser": {**common, "tenant": gate.TENANT, "viewports": [{"width": width, "status": "green", "evidenceRef": f"browser:{width}"} for width in gate.WIDTHS], "formalHttp": True, "keyboard": True, "visibleFocus": True, "noHorizontalOverflow": True, "networkObserved": True, "consoleObserved": True, "authorityVisible": True, "commandsInvoked": 0},
        },
    }


def test_complete_same_release_manifest_allows_next_wave_without_release() -> None:
    decision = gate.evaluate(manifest())
    assert decision["status"] == "GREEN"
    assert decision["action"] == "NEXT_WAVE_ALLOWED"
    assert decision["sideEffectsPerformed"] == []


def test_missing_receipt_fails_closed() -> None:
    value = manifest()
    value["receiptRefs"].pop()
    decision = gate.evaluate(value)
    assert "MISSING_RECEIPT:W3-09" in decision["receiptGate"]["reasons"]


def test_non_ancestor_receipt_cannot_be_cross_release_spliced() -> None:
    value = manifest()
    value["receiptRefs"][3]["isAncestor"] = False
    decision = gate.evaluate(value)
    assert "RECEIPT_NOT_IN_RELEASE:W3-04" in decision["receiptGate"]["reasons"]


@pytest.mark.parametrize("status", ["unknown", "partial", "stale", "blocked", "failed"])
def test_non_green_axis_status_fails_closed(status: str) -> None:
    value = manifest()
    value["axes"]["store"]["status"] = status
    assert gate.evaluate(value)["axes"]["store"]["status"] == "RED"


def test_wrong_positive_tenant_is_rejected() -> None:
    value = manifest()
    value["axes"]["apiSdk"]["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    reasons = gate.evaluate(value)["axes"]["apiSdk"]["reasons"]
    assert "POSITIVE_TENANT_INVALID" in reasons


def test_missing_viewport_and_browser_command_are_independent_red_reasons() -> None:
    value = manifest()
    value["axes"]["browser"]["viewports"].pop()
    value["axes"]["browser"]["commandsInvoked"] = 1
    reasons = gate.evaluate(value)["axes"]["browser"]["reasons"]
    assert "MISSING_VIEWPORT:1920" in reasons
    assert "BROWSER_COMMAND_SIDE_EFFECT" in reasons


@pytest.mark.parametrize("kind", sorted(gate.FORBIDDEN_POSITIVE_KINDS))
def test_synthetic_or_blocked_only_evidence_cannot_close_runtime(kind: str) -> None:
    value = manifest()
    value["axes"]["browser"]["evidenceKind"] = kind
    assert "NON_OPERATIONAL_POSITIVE_EVIDENCE" in gate.evaluate(value)["axes"]["browser"]["reasons"]


def test_hash_mismatch_is_not_hidden_by_green_labels() -> None:
    value = manifest()
    value["axes"]["web"]["webBuildHash"] = "sha256:other"
    assert "WEB_BUILD_HASH_MISMATCH" in gate.evaluate(value)["axes"]["web"]["reasons"]


def test_unknown_field_and_duplicate_receipt_are_rejected() -> None:
    value = manifest()
    value["unexpected"] = True
    with pytest.raises(gate.ManifestError, match="expected keys"):
        gate.evaluate(value)
    value = manifest()
    value["receiptRefs"].append(copy.deepcopy(value["receiptRefs"][0]))
    with pytest.raises(gate.ManifestError, match="duplicate receipt"):
        gate.evaluate(value)
