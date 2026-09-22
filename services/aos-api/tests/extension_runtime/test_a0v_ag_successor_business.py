"""AG registration binds the exact AF detach and current AG runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ag_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ag_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_ag_registration_constants_are_exact_and_new():
    assert successor.AG_ID == "37d36900-5b9a-4cd0-9108-4ef5ded25d58"
    assert successor.AG_GENERATION == "31192641-3558-4cf2-9ad9-ea2375c69900"
    assert successor.AF_ID == "0bf928a9-877a-4b97-9778-7f678d6cd7d4"
    assert successor.AF_GENERATION == "173e267c-f031-4fda-b801-bc9e0a0d2264"
    assert successor.DETACH == "8d157372-308e-468a-876e-d1e03dd0dc56"
    assert successor.KEY.endswith("ag-successor-v1")


def test_registration_requires_group98_legacy_and_ag_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 98' in source
    assert 'row["revision"] != 71' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
