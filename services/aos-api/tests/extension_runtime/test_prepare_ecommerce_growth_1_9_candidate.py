import importlib
import importlib.util
from copy import deepcopy
from pathlib import Path
import sys

import pytest

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.ecommerce_growth_runtime_adapters import _strict_analysis_start_command


@pytest.fixture
def prepare(monkeypatch):
    root = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(str(root / "scripts"))
    return importlib.import_module("prepare_ecommerce_growth_1_9_candidate")


def _load(target, monkeypatch):
    root = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(str(root / "packages/aos-extension-sdk/python"))
    name = "ecommerce_growth_candidate_19_test"
    spec = importlib.util.spec_from_file_location(
        name,
        target / "backend/ecommerce_growth/__init__.py",
        submodule_search_locations=[str(target / "backend/ecommerce_growth")],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return name, module


def _ref(kind):
    return {
        "resourceType": kind,
        "resourceId": "id",
        "revision": 1,
        "contentHash": "sha256:" + "a" * 64,
    }


def test_cannot_overwrite_or_ignore_baseline_or_source_drift(prepare, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="must not exist"):
        prepare.prepare(tmp_path)
    monkeypatch.setattr(prepare, "BASE_HASH", "wrong")
    with pytest.raises(ValueError, match="baseline drifted"):
        prepare.prepare(tmp_path / "baseline")
    monkeypatch.setattr(prepare, "BASE_HASH", prepare.tree_hash(prepare.BASE))
    monkeypatch.setattr(prepare, "AUTHOR_ENTRY_HASH", "wrong")
    with pytest.raises(ValueError, match="registration drifted"):
        prepare.prepare(tmp_path / "entry")
    monkeypatch.setattr(prepare, "AUTHOR_ENTRY_HASH", prepare._sha256(
        (prepare.AUTHOR / "backend/ecommerce_growth/__init__.py").read_bytes()
    ))
    monkeypatch.setattr(prepare, "COPY_SOURCES", {**prepare.COPY_SOURCES,
        "backend/ecommerce_growth/ecommerce_product_event_schedule.py": "wrong"})
    with pytest.raises(ValueError, match="source drifted"):
        prepare.prepare(tmp_path / "source")
    assert all(not (tmp_path / item).exists() for item in ("baseline", "entry", "source"))


def test_candidate_exact_diff_and_manifest_registration(prepare, tmp_path):
    target = tmp_path / "candidate"
    receipt = prepare.prepare(target)
    before = {
        str(path.relative_to(prepare.BASE)): path.read_bytes()
        for path in prepare.BASE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    after = {str(path.relative_to(target)): path.read_bytes() for path in target.rglob("*") if path.is_file()}
    changed = {path for path in before if before[path] != after[path]}
    assert not set(before) - set(after)
    assert changed == {
        "bundle.yaml",
        "backend/ecommerce_growth/__init__.py",
        "backend/ecommerce_growth/ecommerce_business_investigation_application.py",
        *receipt["updatedSelfReferences"],
    }
    assert set(after) - set(before) == set(prepare.COPY_SOURCES) - {
        "backend/ecommerce_growth/ecommerce_business_investigation_application.py"
    }
    loaded = ManifestLoader({"candidate": tmp_path}).load("bundle://candidate/candidate")
    assert loaded.manifest.metadata.version == "1.9.0"
    contributions = [item.model_dump(by_alias=True, mode="json", exclude_none=True)
                     for item in loaded.manifest.spec.contributions]
    assert len(contributions) == 25
    operations = [item["operationId"] for item in contributions if item["kind"] == "api"]
    assert len(operations) == len(set(operations)) == 11
    assert operations[0] == "ecommerce_growth_event_control"
    module = {"__name__": "candidate_entry"}
    exec(compile(after["backend/ecommerce_growth/__init__.py"], "candidate_entry", "exec"), module)
    assert module["register"](object())["contributions"] == contributions
    assert receipt["treeHash"] == "sha256:" + prepare.tree_hash(target)


def test_candidate_runtime_contains_event_and_analysis_domain_logic(prepare, tmp_path, monkeypatch):
    target = tmp_path / "candidate"
    prepare.prepare(target)
    name, package = _load(target, monkeypatch)
    try:
        registration = package.register(object())["contributions"]
        assert len(registration) == 25
        assert any(item.get("operationId") == "ecommerce_growth_event_control" for item in registration)
        schedule = importlib.import_module(name + ".ecommerce_product_event_schedule")
        control = importlib.import_module(name + ".ecommerce_product_event_control")
        application = importlib.import_module(name + ".ecommerce_business_investigation_application")
        assert schedule.ProductEventSchedulePolicy.__name__ == "ProductEventSchedulePolicy"
        assert callable(control.build_event_control_command)
        assert "control_port" in application.EcommerceGrowthApplication.__init__.__annotations__

        request = {
            "kind": "build_analysis_start",
            "occurrenceRef": _ref("AutomationOccurrence"),
            "caseRef": _ref("BusinessInvestigationCaseRevision"),
            "profileRef": _ref("InvestigationProfileRevision"),
            "cutoffAt": "2026-09-16T00:00:00+00:00",
            "idempotencyKey": "candidate-1.9-analysis-start",
        }
        original = deepcopy(request)
        result = package.handle("ecommerce_growth_analysis_advance", request, object())
        _strict_analysis_start_command(result)
        assert request == original
        assert package.handle("ecommerce_growth_analysis_advance", request, object()) == result
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + "."):
                del sys.modules[key]
