"""AD registration binds the exact AC detach and current AD runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ad_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ad_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_ad_registration_constants_are_exact_and_new():
    assert successor.AD_ID == "42d9f8bd-11b0-4f8d-8c4d-75458ab23c94"
    assert successor.AD_GENERATION == "7a2f5483-8ff6-4672-b174-f273885e99d0"
    assert successor.AC_ID == "4fbd0873-dede-4c3c-9db8-29c3e14c2c48"
    assert successor.AC_GENERATION == "cdfa92eb-a695-46e7-9ed4-35a296321403"
    assert successor.DETACH == "328a95b9-7e2a-4ff5-a752-4d61eda4455b"
    assert successor.KEY.endswith("ad-successor-v1")

def test_registration_requires_group89_legacy_and_ad_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 89' in source
    assert 'row["revision"] != 62' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
