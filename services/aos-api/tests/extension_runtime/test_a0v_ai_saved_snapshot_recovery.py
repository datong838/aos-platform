"""AI keeps the saved group and sourceReads zero."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ai_saved_snapshot_recovery.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_ai_saved_snapshot_recovery",PATH);recovery=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(recovery)
def test_exact():
 s=PATH.read_text();assert "current['body']['revision']!=39" in s
 assert "'a0v-ai-saved-input-recovery-v13'" in s and "'recoveries':13" in s
 assert "'pause-failed'" in s and "state='failed'" in s and "revision=508" in s
 assert "'dataset_receipts':12" in s and "'links':0" in s and "'retirements':0" in s
 assert "run_definition" not in s and "'sourceReads':0" in s
