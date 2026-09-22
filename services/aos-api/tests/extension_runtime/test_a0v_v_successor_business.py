"""V registration binds the exact U detach and current V runtime."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_v_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_v_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_v_registration_constants_are_exact_and_new():
    assert successor.V_ID == "33a63ef9-405d-4893-b9f8-dd569f64b46b"
    assert successor.V_GENERATION == "5a9ce3d0-c4c4-4545-a5c7-d286fdb62ddb"
    assert successor.DETACH == "7a9cfacd-e067-4965-a2f3-6e868143ac14"
    assert successor.KEY.endswith("v-successor-v1")


def test_registration_requires_group65_legacy_and_v_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 65' in source
    assert 'row["revision"] != 38' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
