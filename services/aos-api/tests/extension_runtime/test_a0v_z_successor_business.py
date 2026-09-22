"""Z registration binds the exact Y detach and current Z runtime."""
import importlib.util
from pathlib import Path

PATH = Path(__file__).resolve().parents[4] / "scripts/a0v_z_successor_business.py"
SPEC = importlib.util.spec_from_file_location("a0v_z_successor_business", PATH)
successor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(successor)

def test_z_registration_constants_are_exact_and_new():
    assert successor.Z_ID == "cd426e3a-f5e8-45a2-b6a8-8991294b467e"
    assert successor.Z_GENERATION == "d49fe4fd-55c8-4688-9602-5dbff946bc36"
    assert successor.Y_ID == "c76d26b9-8a93-4476-a6fe-206e10930bc9"
    assert successor.DETACH == "0c5b83ce-7374-43ce-802e-799748c08802"
    assert successor.KEY.endswith("z-successor-v1")

def test_registration_requires_group77_legacy_and_z_revision4():
    source = PATH.read_text(encoding="utf-8")
    assert '"expectedGroupRevision": 77' in source
    assert 'row["revision"] != 50' in source
    assert 'binding["revision"] != 4' in source
    assert "UPDATE extension_operation_dispatch_binding" not in source
