#!/usr/bin/env python3
"""Read-only proof that current signed AIP definitions match the current Registry."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

from psycopg import connect
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"


def _preview_module():
    path = ROOT / "scripts/a0v_current_preview_http.py"
    spec = importlib.util.spec_from_file_location("a0v_current_preview_for_aip", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("PREVIEW_PREFLIGHT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preflight(signed_receipt: Path) -> dict[str, object]:
    parameters, report = _preview_module().preflight(signed_receipt=signed_receipt)
    os.environ["AOS_DOTENV_DISABLED"] = "1"
    sys.path.insert(0, str(API_ROOT))
    from aos_api.aip_solution_pack_signed_preflight import inspect_current_signed_source
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.asset_registry.signature import FileTrustRootProvider

    signed_root = Path(str(report["signedRoot"]))
    trust_roots = FileTrustRootProvider(Path(str(report["trustRoots"])))
    reader = RegistrySnapshotReader(
        release_policy=ReleasePolicy(trust_roots=trust_roots),
        connect_factory=lambda: connect(**parameters, row_factory=dict_row),
    )
    loader = ManifestLoader({"a0v-current": signed_root}, trust_roots=trust_roots)
    proof = inspect_current_signed_source(reader=reader, loader=loader, signed_root=signed_root)
    return {
        "outcome": "CURRENT_AIP_DEFINITION_SOURCE_EXACT_READ_ONLY",
        "database": report["database"], "installationId": report["installationId"],
        "runtimeBindings": report["runtimeBindings"],
        "sourceRef": proof.source_ref, "contentHash": proof.content_hash,
        "signatureFingerprint": proof.signature_fingerprint,
        "registrySnapshotHash": proof.registry_snapshot_hash,
        "agents": proof.agent_count, "skills": proof.skill_count,
        "capabilities": proof.capability_count, "writes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signed-receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(preflight(args.signed_receipt), sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "errorType": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
