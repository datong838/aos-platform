"""AC registration binds the exact AB detach and current AC runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ac_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ac_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_ac_registration_constants_are_exact_and_new():
    assert successor.AC_ID == "4fbd0873-dede-4c3c-9db8-29c3e14c2c48"
    assert successor.AC_GENERATION == "cdfa92eb-a695-46e7-9ed4-35a296321403"
    assert successor.AB_ID == "b57e5f93-f075-45f1-a42c-4340255e4f74"
    assert successor.AB_GENERATION == "00fba2de-a505-49f1-a3e6-696d7415fc79"
    assert successor.DETACH == "19cd00c5-25e1-4d8c-befd-618c8035e172"
    assert successor.KEY.endswith("ac-successor-v1")


def test_registration_requires_group86_legacy_and_ac_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 86' in source
    assert 'row["revision"] != 59' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
