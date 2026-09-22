"""AF registration binds the exact AE detach and current AF runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_af_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_af_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_af_registration_constants_are_exact_and_new():
    assert successor.AF_ID == "0bf928a9-877a-4b97-9778-7f678d6cd7d4"
    assert successor.AF_GENERATION == "173e267c-f031-4fda-b801-bc9e0a0d2264"
    assert successor.AE_ID == "d02f90f2-eb0e-4859-ad58-35b17ddbcd6a"
    assert successor.AE_GENERATION == "36a57887-4f28-45e7-8515-2d94a343b5ed"
    assert successor.DETACH == "0f1dd7dd-12ed-4efe-a2c3-49b3f931c1c9"
    assert successor.KEY.endswith("af-successor-v1")


def test_registration_requires_group95_legacy_and_af_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 95' in source
    assert 'row["revision"] != 68' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
