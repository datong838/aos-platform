#!/usr/bin/env python3
"""Compile the W3-10 five-layer cumulative gate without side effects."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable


SCHEMA = "aos-workshop-w3-common-orchestration-gate/v1"
DECISION_SCHEMA = "aos-workshop-w3-common-orchestration-decision/v1"
TENANT = {"orgId": "org-org", "projectId": "dev-project"}
TASKS = tuple(f"W3-{index:02d}" for index in range(1, 10))
WIDTHS = (1280, 1440, 1920)
AXES = ("contract", "store", "apiSdk", "web", "browser")
FORBIDDEN_POSITIVE_KINDS = {
    "blocked_shell",
    "file_url",
    "fixture",
    "mock",
    "sample",
    "static",
    "test_only",
}


class ManifestError(ValueError):
    pass


def _exact(value: dict[str, Any], keys: set[str], path: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        actual = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ManifestError(f"{path}: expected keys {sorted(keys)}, got {actual}")


def _nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{path}: must be a non-empty string")
    return value


def _identity(axis: dict[str, Any], release: dict[str, Any], reasons: list[str]) -> None:
    if axis["releaseId"] != release["id"]:
        reasons.append("RELEASE_ID_MISMATCH")
    if axis["cutoff"] != release["cutoff"]:
        reasons.append("CUTOFF_MISMATCH")
    if axis["evidenceKind"] in FORBIDDEN_POSITIVE_KINDS:
        reasons.append("NON_OPERATIONAL_POSITIVE_EVIDENCE")
    if axis["status"] != "green":
        reasons.append("AXIS_NOT_GREEN")
    if not isinstance(axis["evidenceRefs"], list) or not axis["evidenceRefs"]:
        reasons.append("MISSING_AXIS_EVIDENCE")


def _tenant(axis: dict[str, Any], reasons: list[str]) -> None:
    if axis["tenant"] != TENANT:
        reasons.append("POSITIVE_TENANT_INVALID")


def _receipts(manifest: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for index, receipt in enumerate(manifest["receiptRefs"]):
        _exact(
            receipt,
            {"taskId", "status", "commit", "isAncestor", "evidenceRef"},
            f"receiptRefs[{index}]",
        )
        task = _nonempty(receipt["taskId"], f"receiptRefs[{index}].taskId")
        _nonempty(receipt["evidenceRef"], f"receiptRefs[{index}].evidenceRef")
        if task in seen:
            raise ManifestError(f"duplicate receipt taskId: {task}")
        seen.add(task)
        if receipt["status"] != "green":
            reasons.append(f"RECEIPT_NOT_GREEN:{task}")
        if not isinstance(receipt["commit"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", receipt["commit"]
        ):
            reasons.append(f"INVALID_RECEIPT_COMMIT:{task}")
        if receipt["isAncestor"] is not True:
            reasons.append(f"RECEIPT_NOT_IN_RELEASE:{task}")
    for task in sorted(set(TASKS) - seen):
        reasons.append(f"MISSING_RECEIPT:{task}")
    for task in sorted(seen - set(TASKS)):
        reasons.append(f"UNKNOWN_RECEIPT:{task}")
    return reasons


def _contract(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "releaseId", "cutoff", "status", "evidenceKind", "evidenceRefs",
            "schemaHash", "openapiHash", "exactRefs", "errorsVisible",
        },
        "axes.contract",
    )
    _identity(axis, release, reasons)
    if axis["schemaHash"] != release["schemaHash"]:
        reasons.append("SCHEMA_HASH_MISMATCH")
    if axis["openapiHash"] != release["openapiHash"]:
        reasons.append("OPENAPI_HASH_MISMATCH")
    for field in ("exactRefs", "errorsVisible"):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    return reasons


def _store(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "releaseId", "cutoff", "status", "evidenceKind", "evidenceRefs",
            "tenant", "migrationHead", "rls", "cas", "idempotency",
            "restartReadback", "liveMigrationApplied",
        },
        "axes.store",
    )
    _identity(axis, release, reasons)
    _tenant(axis, reasons)
    if axis["migrationHead"] != release["migrationHead"]:
        reasons.append("MIGRATION_HEAD_MISMATCH")
    for field in ("rls", "cas", "idempotency", "restartReadback"):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    if axis["liveMigrationApplied"] is not False:
        reasons.append("LIVE_MIGRATION_SIDE_EFFECT")
    return reasons


def _api_sdk(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "releaseId", "cutoff", "status", "evidenceKind", "evidenceRefs",
            "tenant", "openapiHash", "strictSdk", "canonicalOperations",
            "failClosedErrors", "formalHttp",
        },
        "axes.apiSdk",
    )
    _identity(axis, release, reasons)
    _tenant(axis, reasons)
    if axis["openapiHash"] != release["openapiHash"]:
        reasons.append("OPENAPI_HASH_MISMATCH")
    for field in ("strictSdk", "canonicalOperations", "failClosedErrors", "formalHttp"):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    return reasons


def _web(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "releaseId", "cutoff", "status", "evidenceKind", "evidenceRefs",
            "tenant", "webBuildHash", "publicPackageUnique", "typedIntents",
            "nineStates", "contributionLineage",
        },
        "axes.web",
    )
    _identity(axis, release, reasons)
    _tenant(axis, reasons)
    if axis["webBuildHash"] != release["webBuildHash"]:
        reasons.append("WEB_BUILD_HASH_MISMATCH")
    for field in ("publicPackageUnique", "typedIntents", "nineStates", "contributionLineage"):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    return reasons


def _browser(axis: dict[str, Any], release: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    _exact(
        axis,
        {
            "releaseId", "cutoff", "status", "evidenceKind", "evidenceRefs",
            "tenant", "viewports", "formalHttp", "keyboard", "visibleFocus",
            "noHorizontalOverflow", "networkObserved", "consoleObserved",
            "authorityVisible", "commandsInvoked",
        },
        "axes.browser",
    )
    _identity(axis, release, reasons)
    _tenant(axis, reasons)
    seen: set[int] = set()
    for index, viewport in enumerate(axis["viewports"]):
        _exact(viewport, {"width", "status", "evidenceRef"}, f"axes.browser.viewports[{index}]")
        width = viewport["width"]
        if width in seen:
            raise ManifestError(f"duplicate browser viewport: {width}")
        seen.add(width)
        if viewport["status"] != "green":
            reasons.append(f"VIEWPORT_NOT_GREEN:{width}")
        if not viewport["evidenceRef"]:
            reasons.append(f"MISSING_VIEWPORT_EVIDENCE:{width}")
    for width in sorted(set(WIDTHS) - seen):
        reasons.append(f"MISSING_VIEWPORT:{width}")
    for width in sorted(seen - set(WIDTHS)):
        reasons.append(f"UNKNOWN_VIEWPORT:{width}")
    for field in (
        "formalHttp", "keyboard", "visibleFocus", "noHorizontalOverflow",
        "networkObserved", "consoleObserved", "authorityVisible",
    ):
        if axis[field] is not True:
            reasons.append(f"{field.upper()}_NOT_GREEN")
    if axis["commandsInvoked"] != 0:
        reasons.append("BROWSER_COMMAND_SIDE_EFFECT")
    return reasons


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    _exact(manifest, {"schema", "release", "receiptRefs", "axes"}, "manifest")
    if manifest["schema"] != SCHEMA:
        raise ManifestError(f"unsupported schema: {manifest['schema']}")
    release = manifest["release"]
    _exact(
        release,
        {"id", "gitCommit", "schemaHash", "openapiHash", "webBuildHash", "migrationHead", "cutoff"},
        "release",
    )
    for key, value in release.items():
        _nonempty(value, f"release.{key}")
    if not re.fullmatch(r"[0-9a-f]{40}", release["gitCommit"]):
        raise ManifestError("release.gitCommit must be a full lowercase Git SHA")
    _exact(manifest["axes"], set(AXES), "axes")
    evaluators: dict[str, Callable[[dict[str, Any], dict[str, Any]], list[str]]] = {
        "contract": _contract,
        "store": _store,
        "apiSdk": _api_sdk,
        "web": _web,
        "browser": _browser,
    }
    decisions = {}
    for name, evaluator in evaluators.items():
        reasons = sorted(set(evaluator(manifest["axes"][name], release)))
        decisions[name] = {"status": "GREEN" if not reasons else "RED", "reasons": reasons}
    receipt_reasons = sorted(set(_receipts(manifest)))
    all_green = not receipt_reasons and all(item["status"] == "GREEN" for item in decisions.values())
    return {
        "schema": DECISION_SCHEMA,
        "releaseId": release["id"],
        "status": "GREEN" if all_green else "RED",
        "action": "NEXT_WAVE_ALLOWED" if all_green else "NO_NEXT_WAVE",
        "receiptGate": {"status": "GREEN" if not receipt_reasons else "RED", "reasons": receipt_reasons},
        "axes": decisions,
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
            "action": "NO_NEXT_WAVE",
            "receiptGate": {"status": "RED", "reasons": [f"INVALID_MANIFEST:{error}"]},
            "axes": {},
            "sideEffectsPerformed": [],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, sort_keys=True))
    return 0 if decision["status"] == "GREEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
