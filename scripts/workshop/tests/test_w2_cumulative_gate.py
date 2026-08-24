from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "w2_cumulative_gate.py"
SPEC = importlib.util.spec_from_file_location("w2_cumulative_gate", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def manifest() -> dict:
    release_id = "w2-release-test"
    cutoff = "2026-08-24T11:00:00Z"
    modules = [
        {"id": module, "status": "green", "evidenceRefs": [f"receipt:{module}"]}
        for module in gate.MODULES
    ]
    pipelines = [
        {
            "id": pipeline,
            "status": "succeeded",
            "latestRunRef": f"run:{pipeline}",
            "freshness": "green",
            "quality": "green",
            "reconciliation": "green",
            "sourceCount": 1,
            "canonicalCount": 1,
            "queryCount": 1,
            "matched": 1,
            "unmatched": 0,
            "ambiguous": 0,
            "excluded": 0,
            "unknown": 0,
            "deduplicated": 0,
        }
        for pipeline in gate.PIPELINES
    ]
    cells = [
        {
            "moduleId": module,
            "width": width,
            "state": state,
            "status": "green",
            "reason": "",
            "contractRef": "",
            "evidenceRef": f"browser:{module}:{width}:{state}",
        }
        for module in gate.MODULES
        for width in gate.WIDTHS
        for state in gate.STATES
    ]
    return {
        "schema": gate.SCHEMA,
        "release": {
            "id": release_id,
            "gitCommit": "a" * 40,
            "bundleRevision": "bundle:1",
            "installationRevision": "install:1",
            "apiRevision": "api:1",
            "schemaRevision": "schema:1",
            "cutoff": cutoff,
        },
        "receiptRefs": [
            {
                "taskId": task,
                "status": "green",
                "releaseId": release_id,
                "evidenceRef": f"delivery:{task}",
            }
            for task in gate.TASKS
        ],
        "axes": {
            "source_data_green": {
                "evidenceKind": "read_only_probe",
                "releaseId": release_id,
                "tenant": gate.TENANT,
                "cutoff": cutoff,
                "pipelines": pipelines,
            },
            "eight_view_contract_green": {
                "evidenceKind": "contract_test",
                "releaseId": release_id,
                "tenant": gate.TENANT,
                "cutoff": cutoff,
                "modules": copy.deepcopy(modules),
            },
            "eight_view_runtime_green": {
                "evidenceKind": "formal_http",
                "releaseId": release_id,
                "tenant": gate.TENANT,
                "cutoff": cutoff,
                "modules": copy.deepcopy(modules),
            },
            "shared_context_timeline_navigation_green": {
                "evidenceKind": "formal_http",
                "releaseId": release_id,
                "tenant": gate.TENANT,
                "cutoff": cutoff,
                "status": "green",
                "refreshRestored": True,
                "historyRestored": True,
                "timelineStable": True,
                "targetsServerResolved": True,
                "evidenceRefs": ["browser:shared-context"],
            },
            "browser_positive_green": {
                "evidenceKind": "formal_http",
                "releaseId": release_id,
                "tenant": gate.TENANT,
                "cutoff": cutoff,
                "cells": cells,
                "keyboard": True,
                "visibleFocus": True,
                "refresh": True,
                "deepLink": True,
                "history": True,
                "zoom200": True,
                "reducedMotion": True,
                "textAlternative": True,
                "networkClean": True,
                "consoleClean": True,
            },
            "security_isolation_green": {
                "evidenceKind": "read_only_probe",
                "releaseId": release_id,
                "cutoff": cutoff,
                "positiveTenant": gate.TENANT,
                "canaryTenant": gate.CANARY,
                "canarySourceCount": 0,
                "canaryProjectionCount": 0,
                "piiScan": "clean",
                "secretScan": "clean",
                "writeRequests": 0,
                "evidenceRefs": ["probe:tenant-isolation"],
            },
        },
    }


def test_all_six_axes_and_receipts_green_allows_release() -> None:
    decision = gate.evaluate(manifest())
    assert decision["status"] == "GREEN"
    assert decision["action"] == "RELEASE_ALLOWED"
    assert decision["sideEffectsPerformed"] == []


@pytest.mark.parametrize("kind", sorted(gate.FORBIDDEN_POSITIVE_KINDS))
def test_fixture_mock_or_test_only_cannot_make_runtime_green(kind: str) -> None:
    value = manifest()
    value["axes"]["eight_view_runtime_green"]["evidenceKind"] = kind
    decision = gate.evaluate(value)
    assert decision["status"] == "RED"
    assert "NON_OPERATIONAL_POSITIVE_EVIDENCE" in decision["axes"]["eight_view_runtime_green"]["reasons"]


def test_pipeline_failure_and_ledger_mismatch_are_independent_red_reasons() -> None:
    value = manifest()
    pipeline = value["axes"]["source_data_green"]["pipelines"][0]
    pipeline["status"] = "failed"
    pipeline["matched"] = 0
    decision = gate.evaluate(value)
    reasons = decision["axes"]["source_data_green"]["reasons"]
    assert "LATEST_RUN_NOT_SUCCEEDED:P01" in reasons
    assert "SOURCE_LEDGER_MISMATCH:P01" in reasons


def test_missing_receipt_is_not_compensated_by_six_green_axes() -> None:
    value = manifest()
    value["receiptRefs"].pop()
    decision = gate.evaluate(value)
    assert decision["receiptGate"]["status"] == "RED"
    assert "MISSING_RECEIPT:W2-09" in decision["receiptGate"]["reasons"]


def test_unknown_receipt_is_not_accepted_as_part_of_the_release_set() -> None:
    value = manifest()
    value["receiptRefs"].append(
        {
            "taskId": "W2-99",
            "status": "green",
            "releaseId": value["release"]["id"],
            "evidenceRef": "delivery:W2-99",
        }
    )
    decision = gate.evaluate(value)
    assert "UNKNOWN_RECEIPT:W2-99" in decision["receiptGate"]["reasons"]


def test_cross_release_receipt_fails_closed() -> None:
    value = manifest()
    value["receiptRefs"][2]["releaseId"] = "another-release"
    decision = gate.evaluate(value)
    assert "RECEIPT_RELEASE_MISMATCH:W2-02" in decision["receiptGate"]["reasons"]


def test_missing_browser_cell_and_canary_visibility_block_release() -> None:
    value = manifest()
    value["axes"]["browser_positive_green"]["cells"].pop()
    value["axes"]["security_isolation_green"]["canaryProjectionCount"] = 1
    decision = gate.evaluate(value)
    assert decision["axes"]["browser_positive_green"]["status"] == "RED"
    assert decision["axes"]["security_isolation_green"]["reasons"] == ["CANARY_NOT_ZERO"]


def test_not_applicable_browser_cell_requires_reason_and_contract() -> None:
    value = manifest()
    cell = value["axes"]["browser_positive_green"]["cells"][0]
    cell["status"] = "not_applicable"
    cell["evidenceRef"] = ""
    decision = gate.evaluate(value)
    assert "INVALID_NA_CELL:ecommerce.operations:1280:loading" in decision["axes"]["browser_positive_green"]["reasons"]


def test_unknown_manifest_field_is_rejected() -> None:
    value = manifest()
    value["unexpected"] = True
    with pytest.raises(gate.ManifestError, match="expected keys"):
        gate.evaluate(value)


def test_duplicate_pipeline_is_rejected() -> None:
    value = manifest()
    value["axes"]["source_data_green"]["pipelines"][1]["id"] = "P01"
    with pytest.raises(gate.ManifestError, match="duplicate pipeline"):
        gate.evaluate(value)
