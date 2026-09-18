"""AL keeps the saved group and sourceReads zero."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_al_saved_snapshot_recovery.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_al_saved_snapshot_recovery",PATH);recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)
def test_exact():
 s=PATH.read_text();assert "current['body']['revision']!=48" in s
 assert "'a0v-al-saved-input-recovery-v16'" in s and "'recoveries':16" in s
 assert "run_definition" not in s and "'sourceReads':0" in s
