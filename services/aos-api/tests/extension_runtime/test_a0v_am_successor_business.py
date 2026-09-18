"""AM registration binds the exact AL detach authority."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_am_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_am_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_exact():
    assert successor.AM_ID == "fd28d180-db24-4568-a848-101fcd3aa3c5"
    assert successor.AL_ID == "071e1c31-c464-4735-952e-17adf0ac97f7"
    assert successor.DETACH == "bd92aa48-77b6-4c34-82f9-0ede171083b3"
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 116' in source
    assert 'row["revision"] != 89' in source
    assert 'row["cutover_group_revision"] != 116' in source
    assert '"running": 0, "unresolved": 0, "runtime_pending": 0' in source
