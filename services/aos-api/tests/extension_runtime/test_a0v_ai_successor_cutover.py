"""AI cutover exact authority."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ai_successor_cutover.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_ai_successor_cutover",PATH);cutover=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cutover)
def test_exact():
 assert cutover.OPERATION=="bbe417ce-4cbe-4cc3-a674-3005b618f32d"
 s=PATH.read_text();assert '"expectedGroupRevision": 104' in s and 'qyh-clean-generation-ai-activation' in s
 assert 'UPDATE extension_operation_dispatch_binding' not in s
