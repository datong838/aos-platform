"""AK keeps the saved group and sourceReads zero."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ak_saved_snapshot_recovery.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_ak_saved_snapshot_recovery",PATH);recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)
def test_exact():
 s=PATH.read_text();assert "current['body']['revision']!=45" in s
 assert "'a0v-ak-saved-input-recovery-v15'" in s and "'recoveries':15" in s
 assert "run_definition" not in s and "'sourceReads':0" in s
