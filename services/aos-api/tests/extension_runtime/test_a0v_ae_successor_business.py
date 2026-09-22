"""AE registration binds the exact AD detach and current AE runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ae_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ae_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_ae_registration_constants_are_exact_and_new():
    assert successor.AE_ID == "d02f90f2-eb0e-4859-ad58-35b17ddbcd6a"
    assert successor.AE_GENERATION == "36a57887-4f28-45e7-8515-2d94a343b5ed"
    assert successor.AD_ID == "42d9f8bd-11b0-4f8d-8c4d-75458ab23c94"
    assert successor.AD_GENERATION == "7a2f5483-8ff6-4672-b174-f273885e99d0"
    assert successor.DETACH == "9723047a-7922-4f3a-af11-384aec92752e"
    assert successor.KEY.endswith("ae-successor-v1")


def test_registration_requires_group92_legacy_and_ae_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 92' in source
    assert 'row["revision"] != 65' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
