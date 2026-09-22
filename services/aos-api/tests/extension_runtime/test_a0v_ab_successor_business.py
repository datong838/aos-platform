"""AB registration binds the exact AA detach and current AB runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ab_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ab_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_ab_registration_constants_are_exact_and_new():
    assert successor.AB_ID == "b57e5f93-f075-45f1-a42c-4340255e4f74"
    assert successor.AB_GENERATION == "00fba2de-a505-49f1-a3e6-696d7415fc79"
    assert successor.AA_ID == "d0476259-7e04-4cf6-ba94-9d7da1c73db0"
    assert successor.DETACH == "a15bc392-0981-4b29-9a63-f02439726c0c"
    assert successor.KEY.endswith("ab-successor-v1")


def test_registration_requires_group83_legacy_and_ab_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 83' in source
    assert 'row["revision"] != 56' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
