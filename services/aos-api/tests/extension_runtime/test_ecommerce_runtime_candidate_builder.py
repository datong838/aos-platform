"""Fail-closed tests for the local ecommerce Candidate OCI builder."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/build_ecommerce_runtime_candidates.py"
SPEC = importlib.util.spec_from_file_location("ecommerce_runtime_candidate_builder", SCRIPT)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def test_default_preflight_never_calls_docker(monkeypatch) -> None:
    monkeypatch.setattr(
        BUILDER,
        "_docker",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Docker called")),
    )
    result = BUILDER.preflight()
    assert result["outcome"] == "PREFLIGHT_GREEN"
    assert (result["bundleCount"], result["runtimeMemberCount"]) == (4, 3)
    assert (result["moduleCount"], result["operationCount"]) == (8, 12)


def test_build_rejects_repository_output_before_engine_access(monkeypatch) -> None:
    monkeypatch.setattr(
        BUILDER,
        "_require_isolated_engine",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("engine accessed")),
    )
    with pytest.raises(BUILDER.CandidateBuildBlocked) as captured:
        BUILDER.build(
            context="colima-aos-extension",
            port=18436,
            output=BUILDER.REPOSITORY_ROOT / "forbidden-output",
        )
    assert captured.value.reason_code == "OUTPUT_MUST_BE_OUTSIDE_REPOSITORY"


def test_sbom_augmentation_is_deterministic_and_deduplicated(tmp_path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    path = evidence / "sbom.json"
    path.write_text(
        json.dumps({"bomFormat": "CycloneDX", "components": []}), encoding="utf-8"
    )
    arguments = {"sdk_hash": "sha256:" + "a" * 64, "base_config_digest": "sha256:" + "b" * 64}
    BUILDER._augment_sbom(tmp_path, **arguments)
    first = path.read_bytes()
    BUILDER._augment_sbom(tmp_path, **arguments)
    assert path.read_bytes() == first
    document = json.loads(first)
    assert [item["name"] for item in document["components"]] == [
        "aos-extension-sdk",
        BUILDER.BASE_IMAGE,
    ]


def test_tree_hash_ignores_python_cache(tmp_path) -> None:
    (tmp_path / "source.py").write_text("value = 1\n", encoding="utf-8")
    before = BUILDER._tree_hash(tmp_path)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "source.pyc").write_bytes(b"unstable")
    assert BUILDER._tree_hash(tmp_path) == before
