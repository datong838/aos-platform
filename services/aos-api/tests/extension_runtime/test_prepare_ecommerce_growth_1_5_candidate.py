from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/prepare_ecommerce_growth_1_5_candidate.py"
SPEC = importlib.util.spec_from_file_location("prepare_growth_1_5", SCRIPT)
assert SPEC and SPEC.loader
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def test_prepare_is_exact_and_preserves_immutable_base(tmp_path) -> None:
    before = PREPARE.tree_hash(PREPARE.BASE)
    target = tmp_path / "candidate"
    result = PREPARE.prepare(target)
    assert result["coordinate"] == "aos/solution.ecommerce.growth@1.5.0"
    assert result["fileCount"] == 87
    assert result["backendTreeHash"] == "sha256:" + PREPARE.AUTHOR_BACKEND_HASH
    assert result["updatedSelfReferences"] == 8
    assert PREPARE.tree_hash(target / "backend") == PREPARE.tree_hash(PREPARE.AUTHOR_BACKEND)
    manifest = (target / "bundle.yaml").read_text(encoding="utf-8")
    assert "  version: 1.5.0\n" in manifest
    assert "经营参谋阶段评审 Runtime Candidate" in manifest
    assert not list(target.rglob("*.pyc"))
    refs = tuple(
        path.read_text(encoding="utf-8")
        for path in sorted((target / "content/workshops").glob("*.json"))
    )
    assert sum("bundle://aos/solution.ecommerce.growth@1.5.0" in raw for raw in refs) == 8
    assert all("bundle://aos/solution.ecommerce.growth@1.4.0" not in raw for raw in refs)
    assert PREPARE.tree_hash(PREPARE.BASE) == before == PREPARE.BASE_TREE_HASH
    with pytest.raises(ValueError, match="must not exist"):
        PREPARE.prepare(target)


def test_prepare_rejects_any_reviewed_input_hash_drift(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(PREPARE, "AUTHOR_BACKEND_HASH", "0" * 64)
    target = tmp_path / "candidate"
    with pytest.raises(RuntimeError, match="author backend"):
        PREPARE.prepare(target)
    assert not target.exists()
