#!/usr/bin/env python3
"""Prepare an unsigned immutable core successor for Qiyuehui recovery."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from prepare_ecommerce_growth_1_5_candidate import tree_hash

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "bundles/candidates/ecommerce/domain.ecommerce.core/1.4.0"
TARGET = BASE.parent / "1.4.3"
BASE_HASH = "9136eeb54182a941908da64f9a7f7cce7fd939ab911f603f49d6c08b66748115"
GENERATED = (
    "evidence/bundle-evals.json", "evidence/sbom.json", "bundle.signature.json",
    "artifacts/runtime-image-index.json", "artifacts/python-dependencies.lock",
)
PROVENANCE = "evidence/content-source-provenance.json"


def _files(root: Path) -> dict[str, bytes]:
    paths = sorted(root.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("candidate symlink drifted")
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"}


def _expected() -> dict[str, bytes]:
    if tree_hash(BASE) != BASE_HASH:
        raise ValueError("reviewed core baseline drifted")
    files = _files(BASE)
    marker = b"  version: 1.4.0\n"
    if files["bundle.yaml"].count(marker) != 1 or any(
        b"bundle://aos/domain.ecommerce.core@1.4.0" in data for data in files.values()
    ):
        raise ValueError("core metadata or self-reference inventory drifted")
    files["bundle.yaml"] = files["bundle.yaml"].replace(marker, b"  version: 1.4.3\n", 1)
    for relative in GENERATED:
        files.pop(relative, None)
    provenance = {
        "status": "UNBUILT_UNSIGNED", "baseVersion": "1.4.0", "version": "1.4.3",
        "baseTreeHash": BASE_HASH, "backendChanged": False,
        "buildEvidenceRequired": ["runtime-image-index", "dependency-lock",
                                  "sbom-validation", "bundle-evals", "signature"],
    }
    files[PROVENANCE] = (json.dumps(provenance, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")) + "\n").encode()
    return files


def validate_candidate(candidate: Path = TARGET) -> None:
    if candidate.is_symlink() or not candidate.is_dir() or _files(candidate) != _expected():
        raise ValueError("reviewed core candidate content drifted")


def prepare(target: Path = TARGET) -> dict[str, object]:
    if not isinstance(target, Path) or target.exists() or target.is_symlink():
        raise ValueError("immutable candidate target already exists")
    expected = _expected()
    with tempfile.TemporaryDirectory(prefix=".qyh-core-143-", dir=target.parent) as temp:
        staged = Path(temp) / "candidate"
        staged.mkdir()
        for relative, data in expected.items():
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        validate_candidate(staged)
        if target.exists() or target.is_symlink() or _expected() != expected:
            raise ValueError("candidate target or baseline changed")
        os.rename(staged, target)
    return {"version": "1.4.3", "state": "UNBUILT_UNSIGNED", "treeHash": tree_hash(target)}


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False, sort_keys=True, indent=2))
