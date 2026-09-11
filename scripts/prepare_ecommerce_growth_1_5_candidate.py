#!/usr/bin/env python3
"""Create the immutable ecommerce growth 1.5.0 source candidate."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE = REPOSITORY_ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.4.0"
AUTHOR_BACKEND = REPOSITORY_ROOT / "bundles/solutions/ecommerce-growth/backend"
TARGET = REPOSITORY_ROOT / "bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0"
BASE_TREE_HASH = "4dc6cfbeadc2c50d9bcdbaf85fc78b0aa9f8174db525c696e6c23dadcfaf43b3"
BASE_BACKEND_HASH = "959f154b717d31c3d09451a2dde9d837993d69aa85be5c7c23afe06cee555649"
AUTHOR_BACKEND_HASH = "0d9a0b6988c1ffbfb79ff4ab2389f4038d81385ab2735389a8a800901c85c302"


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        raw = path.read_bytes()
        relative = str(path.relative_to(root))
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(str(len(raw)).encode("ascii") + b"\0")
        digest.update(raw)
    return digest.hexdigest()


def prepare(target: Path = TARGET) -> dict[str, object]:
    if not isinstance(target, Path) or target.exists():
        raise ValueError("new candidate target must not exist")
    if tree_hash(BASE) != BASE_TREE_HASH or tree_hash(BASE / "backend") != BASE_BACKEND_HASH:
        raise RuntimeError("immutable 1.4.0 candidate baseline drifted")
    if tree_hash(AUTHOR_BACKEND) != AUTHOR_BACKEND_HASH:
        raise RuntimeError("reviewed author backend baseline drifted")
    shutil.copytree(
        BASE,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    try:
        shutil.rmtree(target / "backend")
        shutil.copytree(
            AUTHOR_BACKEND,
            target / "backend",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        manifest = target / "bundle.yaml"
        text = manifest.read_text(encoding="utf-8")
        if text.count("  version: 1.4.0\n") != 1:
            raise RuntimeError("base candidate version marker drifted")
        if text.count("  displayName: 电商增长方案包（W3：六数字同事生产 Profile Candidate）\n") != 1:
            raise RuntimeError("base candidate display name drifted")
        text = text.replace("  version: 1.4.0\n", "  version: 1.5.0\n", 1)
        text = text.replace(
            "  displayName: 电商增长方案包（W3：六数字同事生产 Profile Candidate）\n",
            "  displayName: 电商增长方案包（经营参谋阶段评审 Runtime Candidate）\n",
            1,
        )
        manifest.write_text(text, encoding="utf-8")
        old_ref = b"bundle://aos/solution.ecommerce.growth@1.4.0"
        new_ref = b"bundle://aos/solution.ecommerce.growth@1.5.0"
        self_refs = 0
        for path in sorted((target / "content/workshops").glob("*.json")):
            raw = path.read_bytes()
            count = raw.count(old_ref)
            if count:
                if count != 1:
                    raise RuntimeError("candidate self reference is ambiguous")
                path.write_bytes(raw.replace(old_ref, new_ref))
                self_refs += 1
        if self_refs != 8:
            raise RuntimeError("candidate self reference set drifted")
        if tree_hash(target / "backend") != AUTHOR_BACKEND_HASH:
            raise RuntimeError("generated candidate backend differs from author baseline")
        files = sum(
            1
            for path in target.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
        return {
            "coordinate": "aos/solution.ecommerce.growth@1.5.0",
            "fileCount": files,
            "treeHash": "sha256:" + tree_hash(target),
            "backendTreeHash": "sha256:" + tree_hash(target / "backend"),
            "updatedSelfReferences": self_refs,
        }
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise


if __name__ == "__main__":
    print(prepare())
