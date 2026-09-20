#!/usr/bin/env python3
"""Publish BN patch coordinates with the production a0v-canonical alias."""
from __future__ import annotations

import sys
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a0v_bm_trust_root_rotation as repair  # noqa: E402


BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
PREVIOUS = BASE / "bm-trust-root-rotation"
repair.SOURCE_ROOT = PREVIOUS / "candidates"
repair.STATE = BASE / "bn-canonical-alias-registry"
repair.CANDIDATES = repair.STATE / "candidates"
repair.BUILD = repair.STATE / "build"
repair.SIGNED = repair.STATE / "signed-bundles"
repair.BUILD_RECEIPT = repair.STATE / "build-result.json"
repair.QUALIFICATION_RECEIPT = repair.STATE / "qualification-result.json"
repair.KEY = PREVIOUS / "signing/registry-ed25519.pem"
repair.TRUST = PREVIOUS / "signing/trust-roots.json"
repair.SOURCE_ALIAS = "a0v-canonical"
repair.COORDINATES = (
    ("domain.ecommerce.core", "1.4.1", "1.4.2", "ecommerce_core"),
    ("platform.ecommerce.niushop", "1.23.1", "1.23.2", "ecommerce_niushop"),
    ("solution.ecommerce.growth", "1.10.1", "1.10.2", "ecommerce_growth"),
    ("solution.ecommerce.operations-base", "1.2.1", "1.2.2", None),
)


def artifact_proof() -> dict:
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    try:
        from aos_api.asset_registry.manifest_loader import ManifestLoader
        from aos_api.asset_registry.signature import FileTrustRootProvider
        loader = ManifestLoader(
            {"a0v-canonical": repair.SIGNED},
            trust_roots=FileTrustRootProvider(repair.TRUST).snapshot(),
        )
        proofs = []
        with repair._connect()() as conn:
            for bundle_id, _old, version, package in repair.COORDINATES:
                rows = conn.execute(
                    """SELECT a.relative_path,a.artifact_ref,a.digest,a.size
                         FROM asset_bundle_artifact a
                         JOIN asset_bundle_version v ON v.version_pk=a.version_pk
                         JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
                        WHERE b.publisher='aos' AND b.bundle_id=%s AND v.version=%s
                        ORDER BY a.relative_path""",
                    (bundle_id, version),
                ).fetchall()
                expected_source = f"bundle://a0v-canonical/{bundle_id}/{version}"
                sources = {row["artifact_ref"][: -(len(row["relative_path"]) + 1)] for row in rows}
                if sources != {expected_source}:
                    raise repair.RotationBlocked("ARTIFACT_SOURCE_ALIAS_DRIFT", f"{bundle_id}@{version}")
                if package is None:
                    proofs.append({"bundleId": bundle_id, "version": version,
                                   "sourceRef": expected_source, "runtime": False})
                    continue
                row = next((item for item in rows if item["relative_path"] == "artifacts/runtime-image-index.json"), None)
                if row is None:
                    raise repair.RotationBlocked("RUNTIME_INDEX_MISSING", f"{bundle_id}@{version}")
                raw = loader.read_verified_artifact(expected_source, row["relative_path"],
                    expected_digest=row["digest"], limit=1024 * 1024)
                if len(raw) != row["size"] or "sha256:" + hashlib.sha256(raw).hexdigest() != row["digest"]:
                    raise repair.RotationBlocked("RUNTIME_INDEX_READBACK_DRIFT", f"{bundle_id}@{version}")
                proofs.append({"bundleId": bundle_id, "version": version,
                    "sourceRef": expected_source, "runtime": True,
                    "runtimeIndexDigest": row["digest"], "runtimeIndexSize": row["size"]})
        return {"outcome": "BN_CANONICAL_ALIAS_ARTIFACT_PROOF_GREEN", "proofs": proofs,
                "effects": {"mutationCount": 0, "sourceReadCount": 0, "providerInvocationCount": 0}}
    finally:
        sys.path.remove(str(ROOT / "services/aos-api"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "artifact-proof":
        parser = argparse.ArgumentParser()
        parser.add_argument("action", choices=("artifact-proof",))
        parser.add_argument("--output", type=Path, required=True)
        args = parser.parse_args()
        try:
            result, code = artifact_proof(), 0
        except repair.RotationBlocked as exc:
            result, code = {"outcome": "SAFE_BLOCKED", "reasonCode": exc.reason_code,
                            "message": str(exc)}, 2
        repair._write_once(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(code)
    raise SystemExit(repair.main())
