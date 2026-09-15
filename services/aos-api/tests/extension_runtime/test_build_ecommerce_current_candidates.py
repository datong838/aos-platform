import importlib
from pathlib import Path

import pytest


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "scripts"))
    return importlib.import_module("build_ecommerce_current_candidates")


def test_current_profile_combines_exact_frozen_candidates(profile):
    builder = profile.load_builder()
    result = builder.preflight()

    assert result["operationCount"] == 13
    assert result["moduleCount"] == 8
    assert {item["id"]: item["version"] for item in result["bundles"]} == {
        "domain.ecommerce.core": "1.3.0",
        "platform.ecommerce.niushop": "1.22.0",
        "solution.ecommerce.growth": "1.8.0",
        "solution.ecommerce.operations-base": "1.2.0",
    }


def test_current_profile_does_not_mutate_older_profiles(profile):
    profile.load_builder()
    base = importlib.import_module("build_ecommerce_runtime_candidates")
    ui = importlib.import_module("build_ecommerce_ui_candidates").load_builder()

    assert base.RUNTIME_CASES[1][2] == "1.3.0"
    assert base.RUNTIME_CASES[2][2] == "1.7.0"
    assert base.EXPECTED_RUNTIME_OPERATION_COUNT == 12
    assert ui.RUNTIME_CASES[1][2] == "1.5.0"
    assert ui.RUNTIME_CASES[2][2] == "1.8.0"
    assert ui.EXPECTED_RUNTIME_OPERATION_COUNT == 13


def test_current_profile_refuses_growth_profile_drift(profile, monkeypatch):
    original = profile._load

    def changed(path, name):
        module = original(path, name)
        real_load = module.load_builder

        def load():
            builder = real_load()
            builder.EXPECTED_RUNTIME_OPERATION_COUNT = 14
            return builder

        module.load_builder = load
        return module

    monkeypatch.setattr(profile, "_load", changed)
    with pytest.raises(RuntimeError, match="profile drifted"):
        profile.load_builder()
