#!/usr/bin/env python3
"""Independent core1.4.3/Growth1.13 recovery profile; old releases stay intact."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from prepare_ecommerce_qyh_recovery_core_candidate import ROOT, TARGET, validate_candidate

OLD_CORE = ("domain.ecommerce.core/1.4.0", "domain.ecommerce.core", "1.4.0", "ecommerce_core")
NEW_CORE = ("domain.ecommerce.core/1.4.3", "domain.ecommerce.core", "1.4.3", "ecommerce_core")


def _load_growth_builder():
    path = ROOT / "scripts/build_ecommerce_growth_1_13_candidates.py"
    spec = importlib.util.spec_from_file_location("qyh_recovery_growth_builder", path)
    if spec is None or spec.loader is None:
        raise ValueError("Growth profile unavailable")
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    return profile.load_builder()


def load_builder():
    validate_candidate(TARGET)
    builder = _load_growth_builder()
    if (builder.RUNTIME_CASES.count(OLD_CORE) != 1 or builder.ALL_CASES.count(OLD_CORE) != 1
            or builder.ALL_CASES[:len(builder.RUNTIME_CASES)] != builder.RUNTIME_CASES
            or builder.EXPECTED_RUNTIME_OPERATION_COUNT != 15):
        raise ValueError("current recovery profile drifted")
    builder.RUNTIME_CASES = tuple(NEW_CORE if item == OLD_CORE else item for item in builder.RUNTIME_CASES)
    builder.ALL_CASES = tuple(NEW_CORE if item == OLD_CORE else item for item in builder.ALL_CASES)
    original_preflight = builder.preflight
    original_augment = builder._augment_sbom

    def preflight():
        validate_candidate(builder.CANDIDATE_ROOT / NEW_CORE[0])
        return original_preflight()

    def augment_sbom(bundle: Path, *, sdk_hash: str, base_config_digest: str) -> None:
        if bundle.name == "1.4.3" and bundle.parent.name == "domain.ecommerce.core":
            if bundle.resolve() == TARGET.resolve():
                raise ValueError("build evidence must remain outside candidate source")
            if any((bundle / relative).exists() for relative in (
                "evidence/bundle-evals.json", "evidence/sbom.json",
            )):
                raise ValueError("core build evidence already exists")
            # Original build writes a fresh dependency lock before this hook.
            # Compare every other source file, then check its exact lock too.
            lock = bundle / "artifacts/python-dependencies.lock"
            if lock.exists() and lock.read_bytes() != builder.RUNTIME_LOCK:
                raise ValueError("core dependency lock drifted")
            from prepare_ecommerce_qyh_recovery_core_candidate import _files, _expected
            output_files = _files(bundle)
            output_files.pop("artifacts/python-dependencies.lock", None)
            if output_files != _expected():
                raise ValueError("core build source drifted")
            report = preflight()
            core = next(item for item in report["bundles"] if item["id"] == NEW_CORE[1])
            evaluation = {
                "status": "passed", "failed": 0, "scope": "source-preflight-only",
                "runtimeReadiness": "unverified", "sourceTreeHash": core["sourceTreeHash"],
                "runtimeOperations": core["runtimeOperations"],
                "schemaCompatibilityHash": core["schemaCompatibilityHash"],
                "moduleCount": report["moduleCount"], "operationCount": report["operationCount"],
            }
            (bundle / "evidence/bundle-evals.json").write_text(
                json.dumps(evaluation, sort_keys=True, separators=(",", ":")) + "\n")
            (bundle / "evidence/sbom.json").write_text('{"format":"CycloneDX","components":[]}\n')
        original_augment(bundle, sdk_hash=sdk_hash, base_config_digest=base_config_digest)

    builder.preflight = preflight
    builder._augment_sbom = augment_sbom
    return builder


if __name__ == "__main__":
    raise SystemExit(load_builder().main())
