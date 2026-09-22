"""AA registration binds the exact Z detach and current AA runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_aa_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_aa_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_aa_registration_constants_are_exact_and_new():
    assert successor.AA_ID == "d0476259-7e04-4cf6-ba94-9d7da1c73db0"
    assert successor.AA_GENERATION == "44236c8a-cf56-451c-b620-21c63e48d87e"
    assert successor.Z_ID == "cd426e3a-f5e8-45a2-b6a8-8991294b467e"
    assert successor.DETACH == "ede1ac24-57d2-419b-b647-fc7e115109f4"
    assert successor.KEY.endswith("aa-successor-v1")


def test_registration_requires_group80_legacy_and_aa_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 80' in source
    assert 'row["revision"] != 53' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
