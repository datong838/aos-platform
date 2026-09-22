"""AH cutover exact authority."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ah_successor_cutover.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_ah_successor_cutover",PATH);cutover=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cutover)
def test_exact():
 assert cutover.OPERATION=="61363f30-d575-479b-8865-9d175f28cf5a"
 s=PATH.read_text();assert '"expectedGroupRevision": 101' in s and 'qyh-clean-generation-ah-activation' in s
 assert 'UPDATE extension_operation_dispatch_binding' not in s
