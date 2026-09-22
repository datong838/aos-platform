"""AH registration binds exact AG detach."""
import importlib.util
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ah_successor_business.py"
SPEC=importlib.util.spec_from_file_location("a0v_ah_successor_business",PATH);successor=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(successor)
def test_exact():
 assert successor.AH_ID=="9fe97ea8-275a-47d0-a0f1-d2064a8d62c6"
 assert successor.AG_ID=="37d36900-5b9a-4cd0-9108-4ef5ded25d58"
 assert successor.DETACH=="fc5e9725-e32d-4e54-b3fb-eba4f969aaf8"
 s=PATH.read_text();assert '"expectedGroupRevision": 101' in s and 'row["revision"] != 74' in s
