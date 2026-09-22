"""X registration binds the exact W detach and current X runtime."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_x_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_x_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_x_registration_constants_are_exact_and_new():
    assert successor.X_ID == "651dcf7c-08c1-4511-ae23-6e5e864f2b68"
    assert successor.X_GENERATION == "0663a082-ea85-4110-9730-e13c230cd95c"
    assert successor.W_ID == "79e7c90d-4e3a-43e0-a0ae-b81d75c11e8c"
    assert successor.DETACH == "0b079aa6-8233-45b2-9b9b-dcb661f376bd"
    assert successor.KEY.endswith("x-successor-v1")


def test_registration_requires_group71_legacy_and_x_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 71' in source
    assert 'row["revision"] != 44' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
