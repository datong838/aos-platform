"""AJ cutover exact authority."""
import importlib.util,sys
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_aj_successor_cutover.py";sys.path.insert(0,str(PATH.parent))
SPEC=importlib.util.spec_from_file_location("a0v_aj_successor_cutover",PATH);cutover=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cutover)
def test_exact():
 assert cutover.OPERATION=="32bd127b-134c-41b6-b08b-dd760f208c19"
 s=PATH.read_text();assert '"expectedGroupRevision": 107' in s and 'qyh-clean-generation-aj-activation' in s
 assert 'UPDATE extension_operation_dispatch_binding' not in s
