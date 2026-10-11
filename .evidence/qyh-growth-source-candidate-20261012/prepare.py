#!/usr/bin/env python3
"""Task-local source preparation; no build, signing, publishing or installation."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from hashlib import sha256
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from prepare_ecommerce_growth_1_5_candidate import tree_hash


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.13.0"
TARGET = Path(__file__).resolve().parent / "candidate/solution.ecommerce.growth/1.13.1"
CURRENT = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
BASE_HASH = '5818e50bd8c28900ec324b023243b8289a4ef243413b51fd94437fb7fa1f3167'
BACKEND_DELTA = {'content_capability_runtime.py': '47c06e7c42eb90b00c98efb3ed791bfacef896995892dac0ec66a0b201c3b80f', 'content_artifact_review.py': 'd2bb8dd5a160e77c6b4930e5ab571e81ea2a2ce7696486c7c63c7d1a3dabf15e', 'ecommerce_analyst_stage_eval_report.py': 'c4db063f9cab83a57a5d7b6698fd8d5d33604f229c12ad14ad2f34d4f82dfeae'}


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
        raise ValueError("reviewed 1.13.0 baseline drifted")
    _backend_delta()
    with tempfile.TemporaryDirectory(prefix=".growth-1-13-", dir=target.parent) as temp:
        staged = Path(temp) / target.name
        shutil.copytree(BASE, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        manifest = staged / "bundle.yaml"
        raw = manifest.read_text()
        old = "  version: 1.13.0\n"
        if raw.count(old) != 1:
            raise ValueError("candidate version marker drifted")
        manifest.write_text(raw.replace(old, "  version: 1.13.1\n", 1))
        old_ref = "bundle://aos/solution.ecommerce.growth@1.13.0"
        new_ref = "bundle://aos/solution.ecommerce.growth@1.13.1"
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
            "runtimeReadiness": "BLOCKED_ACCEPTED_STAGE_HOST_NOT_WIRED",
            "tenantPurpose": "电商域 / 栖月汇商贸有限公司 / 八工作台",
            "baseVersion": "1.13.0",
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
    return {"version": "1.13.1", "state": "UNBUILT_UNSIGNED",
            "treeHash": tree_hash(target), "changedSelfReferences": rewritten}


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, sort_keys=True, indent=2))
