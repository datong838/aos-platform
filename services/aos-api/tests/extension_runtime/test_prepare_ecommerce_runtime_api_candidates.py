import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml


SCRIPT = Path(__file__).resolve().parents[4] / "scripts/prepare_ecommerce_runtime_api_candidates.py"
SPEC = importlib.util.spec_from_file_location("prepare_runtime_api_candidates", SCRIPT)
assert SPEC and SPEC.loader
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def test_api_yaml_preserves_complete_registration_identity() -> None:
    operations = (("operation_one", "POST", "/one"), ("operation_two", "GET", "/two"))
    document = yaml.safe_load("contributions:\n" + PREPARE._api_yaml(operations))
    assert document["contributions"] == [
        {"kind": "api", "operationId": "operation_one", "method": "POST", "path": "/one", "mode": "exclusive"},
        {"kind": "api", "operationId": "operation_two", "method": "GET", "path": "/two", "mode": "exclusive"},
    ]


def test_prepare_refuses_to_overwrite_any_immutable_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(PREPARE, "CANDIDATES", tmp_path)
    target = tmp_path / PREPARE.CASES[0][1]
    target.mkdir(parents=True)
    with pytest.raises(ValueError, match="must not exist"):
        PREPARE.prepare()


def test_generated_candidates_match_reviewed_trees(monkeypatch, tmp_path):
    original = PREPARE.CANDIDATES
    for base, *_ in PREPARE.CASES:
        shutil.copytree(original / base, tmp_path / base)
    monkeypatch.setattr(PREPARE, "CANDIDATES", tmp_path)
    assert PREPARE.prepare()["outcome"] == "CANDIDATES_PREPARED"
    for _, target, *_ in PREPARE.CASES:
        assert PREPARE.tree_hash(tmp_path / target) == PREPARE.tree_hash(original / target)
