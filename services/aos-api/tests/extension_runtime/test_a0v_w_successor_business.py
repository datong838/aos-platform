"""W registration binds the exact V detach and current W runtime."""

import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_w_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_w_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_w_registration_constants_are_exact_and_new():
    assert successor.W_ID == "79e7c90d-4e3a-43e0-a0ae-b81d75c11e8c"
    assert successor.W_GENERATION == "b4426dfd-a459-41ad-b1e8-fdc440f788db"
    assert successor.DETACH == "229698c4-8653-49be-9280-a6653a91e7ab"
    assert successor.KEY.endswith("w-successor-v1")


def test_registration_requires_group68_legacy_and_w_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 68' in source
    assert 'row["revision"] != 41' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
