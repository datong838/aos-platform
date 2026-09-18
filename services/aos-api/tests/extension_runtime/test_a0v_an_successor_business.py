"""AN registration binds the exact AM detach authority."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_an_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_an_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_exact():
    assert successor.AN_ID == "7eebbd30-88fe-4c3d-a665-f36c5a9d64bb"
    assert successor.AN_GENERATION == "41223cb2-28f6-4109-bdaf-e009ca084367"
    assert successor.AM_ID == "fd28d180-db24-4568-a848-101fcd3aa3c5"
    assert successor.DETACH == "af6fe6a5-2e88-4b7d-8756-0bc977871a5d"
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 119' in source
    assert 'row["revision"] != 92' in source
    assert 'row["cutover_group_revision"] != 119' in source
    assert '"running": 0, "unresolved": 0, "runtime_pending": 0' in source
