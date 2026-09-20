from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "a0v_bm_trust_root_rotation",
        ROOT / "scripts/a0v_bm_trust_root_rotation.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_builder_is_pinned_to_four_patch_coordinates(monkeypatch, tmp_path):
    module = load_module()
    monkeypatch.setattr(module, "CANDIDATES", tmp_path)

    builder = module._builder()

    assert builder.CANDIDATE_ROOT == tmp_path
    assert builder.EXPECTED_RUNTIME_OPERATION_COUNT == 15
    assert [(item[1], item[2]) for item in builder.ALL_CASES] == [
        ("domain.ecommerce.core", "1.4.1"),
        ("platform.ecommerce.niushop", "1.23.1"),
        ("solution.ecommerce.growth", "1.10.1"),
        ("solution.ecommerce.operations-base", "1.2.1"),
    ]
    assert len(builder.RUNTIME_CASES) == 3


def test_prepare_clones_and_rewrites_only_external_candidates(monkeypatch, tmp_path):
    module = load_module()
    source_root = tmp_path / "source"
    state = tmp_path / "state"
    candidates = state / "candidates"
    monkeypatch.setattr(module, "SOURCE_ROOT", source_root)
    monkeypatch.setattr(module, "STATE", state)
    monkeypatch.setattr(module, "CANDIDATES", candidates)
    monkeypatch.setattr(module, "preflight", lambda: {
        "outcome": "PREFLIGHT_GREEN", "port18181Open": False,
    })

    for bundle_id, old, _new, _package in module.COORDINATES:
        root = source_root / bundle_id / old
        root.mkdir(parents=True)
        (root / "bundle.yaml").write_text(
            f"metadata:\n  id: {bundle_id}\n  version: {old}\n", encoding="utf-8"
        )
        (root / "ref.json").write_text(
            json.dumps({"bundleRef": f"bundle://aos/{bundle_id}@{old}"}), encoding="utf-8"
        )

    class Builder:
        @staticmethod
        def preflight():
            for bundle_id, _old, new, _package in module.COORDINATES:
                assert f"version: {new}" in (candidates / bundle_id / new / "bundle.yaml").read_text()
            return {"outcome": "PREFLIGHT_GREEN"}

    monkeypatch.setattr(module, "_builder", lambda: Builder())
    result = module.prepare()

    assert result["outcome"] == "CANDIDATES_READY"
    for bundle_id, old, new, _package in module.COORDINATES:
        target = candidates / bundle_id / new
        assert target.is_dir()
        assert old not in (target / "bundle.yaml").read_text()
        assert f"@{new}" in (target / "ref.json").read_text()


def test_write_once_rejects_unknown_result_boundary(tmp_path):
    module = load_module()
    path = tmp_path / "result.json"
    module._write_once(path, {"outcome": "GREEN"})
    module._write_once(path, {"outcome": "GREEN"})

    with pytest.raises(module.RotationBlocked, match="result.json") as captured:
        module._write_once(path, {"outcome": "DIFFERENT"})

    assert captured.value.reason_code == "RESULT_ALREADY_EXISTS"
    assert path.stat().st_mode & 0o777 == 0o600
