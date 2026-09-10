#!/usr/bin/env python3
"""A0-V canonical ecommerce first install; preflight is the default mode."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services/aos-api"
RECOVERY_ROOT = REPOSITORY_ROOT.parent / ".aos-recovery-20260910"
DEFAULT_BUILD_DIR = (
    RECOVERY_ROOT / "builds/a0v-ecommerce-runtime-candidates-20260910-v4"
)
DEFAULT_BUILD_RECEIPT = (
    RECOVERY_ROOT / "logs/a0v-ecommerce-runtime-candidate-build-v4.json"
)
DEFAULT_QUALIFICATION_RECEIPT = (
    RECOVERY_ROOT / "logs/a0v-ecommerce-runtime-candidate-qualification-v4.json"
)
BUILDER_PATH = REPOSITORY_ROOT / "scripts/build_ecommerce_runtime_candidates.py"
SCOPED_SOURCE_PATHS = (
    "bundles/candidates/ecommerce/domain.ecommerce.core/1.1.0",
    "bundles/candidates/ecommerce/platform.ecommerce.niushop/1.1.0",
    "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0",
    "bundles/candidates/ecommerce/solution.ecommerce.operations-base/1.2.0",
    "scripts/build_ecommerce_runtime_candidates.py",
)
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
EXPECTED_DATABASE = "aos_meta_head"
PLATFORM = "linux/arm64"
EXPECTED_EFFECTS = {
    "registryPublishCount": 0,
    "installationMutationCount": 0,
    "providerInvocationCount": 0,
    "externalPublicationCount": 0,
}
EXPECTED_TAMPER_REJECTIONS = (
    "imageIndexBytes",
    "imageDigest",
    "dependencyLock",
    "sbom",
    "backend",
    "schemaCompatibility",
    "schemaRequirements",
)


class FirstInstallBlocked(RuntimeError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--build-receipt", type=Path, default=DEFAULT_BUILD_RECEIPT)
    parser.add_argument(
        "--qualification-receipt",
        type=Path,
        default=DEFAULT_QUALIFICATION_RECEIPT,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, reason_code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FirstInstallBlocked(reason_code, str(path)) from exc
    if not isinstance(value, dict):
        raise FirstInstallBlocked(reason_code, str(path))
    return value


def _load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_candidate_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise FirstInstallBlocked("BUILDER_UNAVAILABLE", str(BUILDER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *arguments], cwd=REPOSITORY_ROOT, text=True, stderr=subprocess.PIPE
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise FirstInstallBlocked("SOURCE_REVISION_INVALID", "git verification failed") from exc


def _verify_source_revision(receipt_head: str) -> str:
    if not isinstance(receipt_head, str) or len(receipt_head) != 40:
        raise FirstInstallBlocked("BUILD_RECEIPT_GIT_HEAD_INVALID", "invalid git head")
    current_head = _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", receipt_head, current_head)
    if _git("diff", "--name-only", f"{receipt_head}..{current_head}", "--", *SCOPED_SOURCE_PATHS):
        raise FirstInstallBlocked(
            "CANDIDATE_SOURCE_ADVANCED_AFTER_BUILD",
            "candidate source or builder changed after the bound build",
        )
    if _git("status", "--porcelain", "--untracked-files=all", "--", *SCOPED_SOURCE_PATHS):
        raise FirstInstallBlocked(
            "CANDIDATE_SOURCE_DIRTY", "candidate source or builder has local changes"
        )
    return current_head


def verify_v4_inputs(
    *, build_dir: Path, build_receipt_path: Path, qualification_receipt_path: Path
) -> dict[str, Any]:
    builder = _load_builder()
    try:
        build_dir = build_dir.resolve(strict=True)
    except OSError as exc:
        raise FirstInstallBlocked("BUILD_OUTPUT_MISSING", str(build_dir)) from exc
    if build_dir == REPOSITORY_ROOT or build_dir.is_relative_to(REPOSITORY_ROOT):
        raise FirstInstallBlocked("BUILD_OUTPUT_NOT_ISOLATED", str(build_dir))
    build_receipt_path = build_receipt_path.resolve(strict=True)
    qualification_receipt_path = qualification_receipt_path.resolve(strict=True)
    build = _read_json(build_receipt_path, "BUILD_RECEIPT_INVALID")
    qualification = _read_json(
        qualification_receipt_path, "QUALIFICATION_RECEIPT_INVALID"
    )
    if (
        build.get("outcome") != "BUILD_GREEN"
        or build.get("output") != str(build_dir)
        or build.get("outputTreeHash") != builder._tree_hash(build_dir)
        or build.get("contentHashes") != builder._content_hashes(build_dir)
        or build.get("effects") != EXPECTED_EFFECTS
        or (build.get("engine") or {}).get("platform") != PLATFORM
    ):
        raise FirstInstallBlocked("BUILD_RECEIPT_MISMATCH", str(build_receipt_path))
    current_head = _verify_source_revision(build.get("gitHead"))
    expected_qualification = {
        "outcome": "QUALIFICATION_GREEN",
        "gitHead": build["gitHead"],
        "buildReceipt": str(build_receipt_path),
        "buildReceiptHash": _sha256(build_receipt_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "ephemeralSignaturePersisted": False,
        "effects": EXPECTED_EFFECTS,
    }
    for key, expected in expected_qualification.items():
        if qualification.get(key) != expected:
            raise FirstInstallBlocked(
                "QUALIFICATION_RECEIPT_MISMATCH", f"qualification field drift: {key}"
            )
    if tuple(qualification.get("tamperRejections") or ()) != EXPECTED_TAMPER_REJECTIONS:
        raise FirstInstallBlocked(
            "QUALIFICATION_TAMPER_MATRIX_MISMATCH", "tamper matrix drifted"
        )
    resolved = {
        (item.get("id"), item.get("version"))
        for item in qualification.get("resolved") or ()
        if isinstance(item, dict)
    }
    expected_resolved = {
        ("domain.ecommerce.core", "1.1.0"),
        ("platform.ecommerce.niushop", "1.1.0"),
        ("solution.ecommerce.growth", "1.4.0"),
        ("solution.ecommerce.operations-base", "1.2.0"),
    }
    if resolved != expected_resolved:
        raise FirstInstallBlocked("QUALIFICATION_RESOLUTION_MISMATCH", str(resolved))
    schema_requirements = qualification.get("schemaRequirements")
    runtime_admissions = qualification.get("runtimeAdmissions")
    if not isinstance(schema_requirements, dict) or set(schema_requirements) != {
        item[0] for item in expected_resolved if item[0] != "solution.ecommerce.operations-base"
    }:
        raise FirstInstallBlocked("SCHEMA_REQUIREMENTS_MISMATCH", "runtime schema set drifted")
    if not isinstance(runtime_admissions, dict) or set(runtime_admissions) != set(
        schema_requirements
    ):
        raise FirstInstallBlocked("RUNTIME_ADMISSIONS_MISMATCH", "runtime set drifted")
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "orgId": ORG_ID,
        "projectId": PROJECT_ID,
        "canaryOrgId": CANARY_ORG_ID,
        "canaryProjectId": CANARY_PROJECT_ID,
        "buildGitHead": build["gitHead"],
        "currentGitHead": current_head,
        "buildOutput": str(build_dir),
        "buildReceiptHash": _sha256(build_receipt_path.read_bytes()),
        "qualificationReceiptHash": _sha256(qualification_receipt_path.read_bytes()),
        "outputTreeHash": build["outputTreeHash"],
        "contentHashes": build["contentHashes"],
        "runtimeAdmissions": runtime_admissions,
        "schemaRequirements": schema_requirements,
        "moduleCount": 8,
        "runtimeMemberCount": 3,
        "effects": EXPECTED_EFFECTS,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    evidence = verify_v4_inputs(
        build_dir=args.build_dir,
        build_receipt_path=args.build_receipt,
        qualification_receipt_path=args.qualification_receipt,
    )
    if not args.apply:
        return evidence
    if args.database_name != EXPECTED_DATABASE:
        raise FirstInstallBlocked(
            "EXPLICIT_ISOLATED_DATABASE_REQUIRED", EXPECTED_DATABASE
        )
    raise FirstInstallBlocked(
        "APPLY_NOT_IMPLEMENTED",
        "canonical apply remains closed until database, signing and lifecycle stages are wired",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evidence = run(args)
    except FirstInstallBlocked as exc:
        evidence = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": exc.reason_code,
            "message": str(exc),
        }
        status = 2
    else:
        status = 0
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
