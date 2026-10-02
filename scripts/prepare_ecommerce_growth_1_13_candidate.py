#!/usr/bin/env python3
"""Prepare an unsigned Growth successor from the reviewed 1.12 candidate."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.12.0"
TARGET = BASE.parent / "1.13.0"
CURRENT = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
BASE_HASH = "5175c24ccd010428e5c4cf54c6cee9d92ec8ccb4cc9ccb92a5c88a55288e0017"
BACKEND_DELTA = {
    "__init__.py": "9f53572116ae6ac0471f1d69639af97593da15c29d2e28449561ddce4195736b",
    "ecommerce_business_investigation_handoff.py": "720896c2ee3ffc8a3f8dcf85cc89b7b3428f5f2f36e4debba73e9c79788c009e",
    "ecommerce_business_investigation_review_command.py": "514ae624b17b38393034398a60067584e446f9b773bb412ac2ddcdd2c4547d2f",
    "ecommerce_content_campaign_workflow_contracts.py": "77b6eab31bc67ea7c48dd07037d731e262541947762269acc9344d259d3881ef",
    "analyst_structure_eval_operation.py": "fb21a939bfa66846012a89fb89df802420fa4bc03be37199346b54869bb160d5",
}


def _backend_delta() -> None:
    base_backend = BASE / "backend/ecommerce_growth"
    old = {path.name: sha256(path.read_bytes()).hexdigest()
           for path in base_backend.glob("*.py")}
    current = {path.name: sha256(path.read_bytes()).hexdigest()
               for path in CURRENT.glob("*.py")}
    changed = {name for name in old.keys() | current.keys()
               if old.get(name) != current.get(name)}
    if changed != BACKEND_DELTA.keys() or any(
        current.get(name) != expected for name, expected in BACKEND_DELTA.items()
    ):
        raise ValueError("reviewed backend delta drifted")


def prepare(target: Path = TARGET) -> dict[str, object]:
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError("immutable candidate target already exists")
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError("reviewed 1.12.0 baseline drifted")
    _backend_delta()
    with tempfile.TemporaryDirectory(prefix=".growth-1-13-", dir=target.parent) as temp:
        staged = Path(temp) / target.name
        shutil.copytree(BASE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        manifest = staged / "bundle.yaml"
        raw = manifest.read_text()
        old = "  version: 1.12.0\n"
        if raw.count(old) != 1:
            raise ValueError("candidate version marker drifted")
        manifest.write_text(raw.replace(old, "  version: 1.13.0\n", 1))
        old_ref = "bundle://aos/solution.ecommerce.growth@1.12.0"
        new_ref = "bundle://aos/solution.ecommerce.growth@1.13.0"
        rewritten = []
        for path in sorted((staged / "content/workshops").glob("*.json")):
            raw = path.read_text()
            if old_ref in raw:
                if raw.count(old_ref) != 1:
                    raise ValueError("candidate self-reference drifted")
                path.write_text(raw.replace(old_ref, new_ref, 1))
                rewritten.append(path.relative_to(staged).as_posix())
        if len(rewritten) != 8:
            raise ValueError("candidate self-reference inventory drifted")
        for name in BACKEND_DELTA:
            (staged / "backend/ecommerce_growth" / name).write_bytes((CURRENT / name).read_bytes())
        for relative in (
            "evidence/bundle-evals.json", "evidence/sbom.json", "bundle.signature.json",
            "artifacts/runtime-image-index.json", "artifacts/python-dependencies.lock",
        ):
            (staged / relative).unlink(missing_ok=True)
        provenance = {
            "status": "UNBUILT_UNSIGNED",
            "baseVersion": "1.12.0",
            "baseTreeHash": BASE_HASH,
            "backendSourceSha256": BACKEND_DELTA,
            "buildEvidenceRequired": ["runtime-image-index", "dependency-lock",
                                      "sbom-validation", "bundle-evals", "signature"],
        }
        (staged / "evidence/content-source-provenance.json").write_text(
            json.dumps(provenance, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n"
        )
        if target.exists() or target.is_symlink() or tree_hash(BASE) != BASE_HASH:
            raise ValueError("candidate target or historical baseline changed")
        _backend_delta()
        os.rename(staged, target)
    return {"version": "1.13.0", "state": "UNBUILT_UNSIGNED",
            "treeHash": tree_hash(target), "changedSelfReferences": rewritten}


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, sort_keys=True, indent=2))
