"""Y registration binds the exact X detach and current Y runtime."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_y_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_y_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_y_registration_constants_are_exact_and_new():
    assert successor.Y_ID == "c76d26b9-8a93-4476-a6fe-206e10930bc9"
    assert successor.Y_GENERATION == "87cd4104-999d-4224-b1ee-772b22a05445"
    assert successor.X_ID == "651dcf7c-08c1-4511-ae23-6e5e864f2b68"
    assert successor.DETACH == "490cce1d-9fc7-42bf-b8ca-aaaa9ac260fc"
    assert successor.KEY.endswith("y-successor-v1")


def test_registration_requires_group74_legacy_and_y_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 74' in source
    assert 'row["revision"] != 47' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
