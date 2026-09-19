"""AO registration binds the exact AN detach authority."""
import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_ao_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_ao_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)


def test_exact():
    assert successor.AO_ID == "d4186607-c93f-4fd0-8daa-46e349184ab9"
    assert successor.AO_GENERATION == "00bb99df-d436-483d-86df-496718c6f129"
    assert successor.AN_ID == "7eebbd30-88fe-4c3d-a665-f36c5a9d64bb"
    assert successor.DETACH == "79254572-7c39-469e-860b-1ae2f36b4b6e"
    assert successor.DETACH_HASH == "sha256:f28bc0f92775768a3aa7c6354cb03f5f7b77f61353888e3116f60014232678f4"
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 122' in source
    assert 'row["revision"] != 95' in source
    assert 'row["cutover_group_revision"] != 122' in source
    assert '(old[0]["revision"], old[0]["execution_epoch"]) != (9, 5)' in source
    assert '"running": 0, "unresolved": 0, "runtime_pending": 0' in source
