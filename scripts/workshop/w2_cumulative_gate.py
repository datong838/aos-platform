#!/usr/bin/env python3
"""Evaluate the W2 six-axis cumulative release gate without side effects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "aos-workshop-w2-cumulative-gate/v1"
DECISION_SCHEMA = "aos-workshop-w2-cumulative-gate-decision/v1"
TENANT = {"orgId": "org-org", "projectId": "dev-project"}
CANARY = {"orgId": "dev-org", "projectId": "dev-project"}
TASKS = tuple(f"W2-{index:02d}" for index in range(10))
PIPELINES = tuple(f"P{index:02d}" for index in range(1, 13))
MODULES = (
    "ecommerce.operations",
    "ecommerce.task-cockpit",
    "ecommerce.content-campaign",
    "ecommerce.creator-growth",
    "ecommerce.media-studio",
    "ecommerce.analyst",
    "ecommerce.price-governance",
    "ecommerce.customer",
)
WIDTHS = (1280, 1440, 1920)
STATES = (
    "loading",
    "empty",
    "forbidden",
    "stale",
    "partial",
    "failed",
    "unknown",
    "blocked",
    "ready",
)
AXES = (
    "source_data_green",
    "eight_view_contract_green",
    "eight_view_runtime_green",
    "shared_context_timeline_navigation_green",
    "browser_positive_green",
    "security_isolation_green",
)
FORBIDDEN_POSITIVE_KINDS = {
    "fixture",
    "mock",
    "sample",
    "static",
    "file_url",
    "blocked_shell",
    "test_only",
}


class ManifestError(ValueError):
    pass


def _exact(value: dict[str, Any], keys: set[str], path: str) -> None:
    actual = set(value)
    if actual != keys:
        raise ManifestError(
            f"{path}: expected keys {sorted(keys)}, got {sorted(actual)}"
        )


def _nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{path}: must be a non-empty string")
    return value


def _same_release(axis: dict[str, Any], release_id: str, reasons: list[str]) -> None:
    if axis["releaseId"] != release_id:
        reasons.append("RELEASE_ID_MISMATCH")


def _real_kind(axis: dict[str, Any], reasons: list[str]) -> None:
    if axis["evidenceKind"] in FORBIDDEN_POSITIVE_KINDS:
        reasons.append("NON_OPERATIONAL_POSITIVE_EVIDENCE")


def _evaluate_receipts(manifest: dict[str, Any], reasons: list[str]) -> None:
    release_id = manifest["release"]["id"]
    seen: set[str] = set()
    for index, receipt in enumerate(manifest["receiptRefs"]):
        _exact(
            receipt,
            {"taskId", "status", "releaseId", "evidenceRef"},
            f"receiptRefs[{index}]",
        )
        task_id = _nonempty(receipt["taskId"], f"receiptRefs[{index}].taskId")
        _nonempty(receipt["evidenceRef"], f"receiptRefs[{index}].evidenceRef")
        if task_id in seen:
            raise ManifestError(f"duplicate receipt taskId: {task_id}")
        seen.add(task_id)
        if receipt["status"] != "green":
            reasons.append(f"RECEIPT_NOT_GREEN:{task_id}")
        if receipt["releaseId"] != release_id:
            reasons.append(f"RECEIPT_RELEASE_MISMATCH:{task_id}")
    for missing in sorted(set(TASKS) - seen):
        reasons.append(f"MISSING_RECEIPT:{missing}")
    for extra in sorted(seen - set(TASKS)):
        reasons.append(f"UNKNOWN_RECEIPT:{extra}")


def _source_axis(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {"evidenceKind", "releaseId", "tenant", "cutoff", "pipelines"},
        "axes.source_data_green",
    )
    _same_release(axis, release["id"], reasons)
    _real_kind(axis, reasons)
    if axis["tenant"] != TENANT:
        reasons.append("POSITIVE_TENANT_INVALID")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    seen: set[str] = set()
    for index, item in enumerate(axis["pipelines"]):
        _exact(
            item,
            {
                "id",
                "status",
                "latestRunRef",
                "freshness",
                "quality",
                "reconciliation",
                "sourceCount",
                "canonicalCount",
                "queryCount",
                "matched",
                "unmatched",
                "ambiguous",
                "excluded",
                "unknown",
                "deduplicated",
            },
            f"axes.source_data_green.pipelines[{index}]",
        )
        pipeline_id = item["id"]
        if pipeline_id in seen:
            raise ManifestError(f"duplicate pipeline id: {pipeline_id}")
        seen.add(pipeline_id)
        _nonempty(item["latestRunRef"], f"pipeline {pipeline_id} latestRunRef")
        if item["status"] != "succeeded":
            reasons.append(f"LATEST_RUN_NOT_SUCCEEDED:{pipeline_id}")
        for field in ("freshness", "quality", "reconciliation"):
            if item[field] != "green":
                reasons.append(f"{field.upper()}_NOT_GREEN:{pipeline_id}")
        counts = (
            "sourceCount",
            "canonicalCount",
            "queryCount",
            "matched",
            "unmatched",
            "ambiguous",
            "excluded",
            "unknown",
            "deduplicated",
        )
        if any(not isinstance(item[field], int) or item[field] < 0 for field in counts):
            reasons.append(f"INVALID_COUNT:{pipeline_id}")
            continue
        classified = sum(
            item[field]
            for field in (
                "matched",
                "unmatched",
                "ambiguous",
                "excluded",
                "unknown",
                "deduplicated",
            )
        )
        if item["sourceCount"] != classified:
            reasons.append(f"SOURCE_LEDGER_MISMATCH:{pipeline_id}")
        if item["canonicalCount"] != item["queryCount"]:
            reasons.append(f"QUERY_LEDGER_MISMATCH:{pipeline_id}")
    for missing in sorted(set(PIPELINES) - seen):
        reasons.append(f"MISSING_PIPELINE:{missing}")
    for extra in sorted(seen - set(PIPELINES)):
        reasons.append(f"UNKNOWN_PIPELINE:{extra}")
    return reasons


def _module_axis(
    name: str,
    axis: dict[str, Any],
    release: dict[str, Any],
    *,
    require_real: bool,
) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {"evidenceKind", "releaseId", "tenant", "cutoff", "modules"},
        f"axes.{name}",
    )
    _same_release(axis, release["id"], reasons)
    if require_real:
        _real_kind(axis, reasons)
    if axis["tenant"] != TENANT:
        reasons.append("POSITIVE_TENANT_INVALID")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    seen: set[str] = set()
    for index, item in enumerate(axis["modules"]):
        _exact(item, {"id", "status", "evidenceRefs"}, f"axes.{name}.modules[{index}]")
        module_id = item["id"]
        if module_id in seen:
            raise ManifestError(f"duplicate module id in {name}: {module_id}")
        seen.add(module_id)
        if item["status"] != "green":
            reasons.append(f"MODULE_NOT_GREEN:{module_id}")
        if not isinstance(item["evidenceRefs"], list) or not item["evidenceRefs"]:
            reasons.append(f"MISSING_MODULE_EVIDENCE:{module_id}")
    for missing in sorted(set(MODULES) - seen):
        reasons.append(f"MISSING_MODULE:{missing}")
    for extra in sorted(seen - set(MODULES)):
        reasons.append(f"UNKNOWN_MODULE:{extra}")
    return reasons


def _shared_axis(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "evidenceKind",
            "releaseId",
            "tenant",
            "cutoff",
            "status",
            "refreshRestored",
            "historyRestored",
            "timelineStable",
            "targetsServerResolved",
            "evidenceRefs",
        },
        "axes.shared_context_timeline_navigation_green",
    )
    _same_release(axis, release["id"], reasons)
    _real_kind(axis, reasons)
    if axis["tenant"] != TENANT:
        reasons.append("POSITIVE_TENANT_INVALID")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    for field in (
        "refreshRestored",
        "historyRestored",
        "timelineStable",
        "targetsServerResolved",
    ):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    if axis["status"] != "green" or not axis["evidenceRefs"]:
        reasons.append("SHARED_CONTEXT_NOT_GREEN")
    return reasons


def _browser_axis(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "evidenceKind",
            "releaseId",
            "tenant",
            "cutoff",
            "cells",
            "keyboard",
            "visibleFocus",
            "refresh",
            "deepLink",
            "history",
            "zoom200",
            "reducedMotion",
            "textAlternative",
            "networkClean",
            "consoleClean",
        },
        "axes.browser_positive_green",
    )
    _same_release(axis, release["id"], reasons)
    _real_kind(axis, reasons)
    if axis["tenant"] != TENANT:
        reasons.append("POSITIVE_TENANT_INVALID")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    expected = {
        (module, width, state)
        for module in MODULES
        for width in WIDTHS
        for state in STATES
    }
    seen: set[tuple[str, int, str]] = set()
    for index, cell in enumerate(axis["cells"]):
        _exact(
            cell,
            {
                "moduleId",
                "width",
                "state",
                "status",
                "reason",
                "contractRef",
                "evidenceRef",
            },
            f"axes.browser_positive_green.cells[{index}]",
        )
        key = (cell["moduleId"], cell["width"], cell["state"])
        if key in seen:
            raise ManifestError(f"duplicate browser matrix cell: {key}")
        seen.add(key)
        if cell["status"] == "green":
            if not cell["evidenceRef"]:
                reasons.append(f"MISSING_CELL_EVIDENCE:{key[0]}:{key[1]}:{key[2]}")
        elif cell["status"] == "not_applicable":
            if not cell["reason"] or not cell["contractRef"]:
                reasons.append(f"INVALID_NA_CELL:{key[0]}:{key[1]}:{key[2]}")
        else:
            reasons.append(f"CELL_NOT_GREEN:{key[0]}:{key[1]}:{key[2]}")
        if cell["state"] == "ready" and cell["status"] != "green":
            reasons.append(f"READY_CELL_NOT_GREEN:{key[0]}:{key[1]}")
    for module, width, state in sorted(expected - seen):
        reasons.append(f"MISSING_MATRIX_CELL:{module}:{width}:{state}")
    for module, width, state in sorted(seen - expected):
        reasons.append(f"UNKNOWN_MATRIX_CELL:{module}:{width}:{state}")
    for field in (
        "keyboard",
        "visibleFocus",
        "refresh",
        "deepLink",
        "history",
        "zoom200",
        "reducedMotion",
        "textAlternative",
        "networkClean",
        "consoleClean",
    ):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    return reasons


def _security_axis(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "evidenceKind",
            "releaseId",
            "cutoff",
            "positiveTenant",
            "canaryTenant",
            "canarySourceCount",
            "canaryProjectionCount",
            "piiScan",
            "secretScan",
            "writeRequests",
            "evidenceRefs",
        },
        "axes.security_isolation_green",
    )
    _same_release(axis, release["id"], reasons)
    _real_kind(axis, reasons)
    if axis["positiveTenant"] != TENANT or axis["canaryTenant"] != CANARY:
        reasons.append("TENANT_PAIR_INVALID")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    if axis["canarySourceCount"] != 0 or axis["canaryProjectionCount"] != 0:
        reasons.append("CANARY_NOT_ZERO")
    if axis["piiScan"] != "clean":
        reasons.append("PII_SCAN_NOT_CLEAN")
    if axis["secretScan"] != "clean":
        reasons.append("SECRET_SCAN_NOT_CLEAN")
    if axis["writeRequests"] != 0:
        reasons.append("WRITE_REQUEST_DETECTED")
    if not axis["evidenceRefs"]:
        reasons.append("MISSING_SECURITY_EVIDENCE")
    return reasons


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    _exact(manifest, {"schema", "release", "receiptRefs", "axes"}, "manifest")
    if manifest["schema"] != SCHEMA:
        raise ManifestError(f"unsupported schema: {manifest['schema']}")
    release = manifest["release"]
    _exact(
        release,
        {
            "id",
            "gitCommit",
            "bundleRevision",
            "installationRevision",
            "apiRevision",
            "schemaRevision",
            "cutoff",
        },
        "release",
    )
    for key, value in release.items():
        _nonempty(value, f"release.{key}")
    _exact(manifest["axes"], set(AXES), "axes")

    receipt_reasons: list[str] = []
    _evaluate_receipts(manifest, receipt_reasons)
    axes = manifest["axes"]
    evaluations = {
        "source_data_green": _source_axis(axes["source_data_green"], release),
        "eight_view_contract_green": _module_axis(
            "eight_view_contract_green",
            axes["eight_view_contract_green"],
            release,
            require_real=False,
        ),
        "eight_view_runtime_green": _module_axis(
            "eight_view_runtime_green",
            axes["eight_view_runtime_green"],
            release,
            require_real=True,
        ),
        "shared_context_timeline_navigation_green": _shared_axis(
            axes["shared_context_timeline_navigation_green"], release
        ),
        "browser_positive_green": _browser_axis(
            axes["browser_positive_green"], release
        ),
        "security_isolation_green": _security_axis(
            axes["security_isolation_green"], release
        ),
    }
    axis_decisions = {
        name: {"status": "GREEN" if not reasons else "RED", "reasons": sorted(set(reasons))}
        for name, reasons in evaluations.items()
    }
    all_green = not receipt_reasons and all(
        item["status"] == "GREEN" for item in axis_decisions.values()
    )
    return {
        "schema": DECISION_SCHEMA,
        "releaseId": release["id"],
        "status": "GREEN" if all_green else "RED",
        "action": "RELEASE_ALLOWED" if all_green else "NO_RELEASE",
        "receiptGate": {
            "status": "GREEN" if not receipt_reasons else "RED",
            "reasons": sorted(set(receipt_reasons)),
        },
        "axes": axis_decisions,
        "sideEffectsPerformed": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.input.read_text(encoding="utf-8"))
    try:
        decision = evaluate(manifest)
    except (ManifestError, TypeError, KeyError) as error:
        decision = {
            "schema": DECISION_SCHEMA,
            "releaseId": manifest.get("release", {}).get("id", "unknown"),
            "status": "RED",
            "action": "NO_RELEASE",
            "receiptGate": {"status": "RED", "reasons": [f"INVALID_MANIFEST:{error}"]},
            "axes": {},
            "sideEffectsPerformed": [],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0 if decision["status"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
