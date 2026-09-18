"""AL registration binds exact AK detach."""
import importlib.util
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_al_successor_business.py"
SPEC=importlib.util.spec_from_file_location("a0v_al_successor_business",PATH);successor=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(successor)
def test_exact():
 assert successor.AL_ID=="071e1c31-c464-4735-952e-17adf0ac97f7"
 assert successor.AK_ID=="038bd251-e2e3-415d-8706-955de809b4df"
 assert successor.DETACH=="ec99c80b-ad80-47aa-af4a-4fb45fd0602d"
 s=PATH.read_text();assert '"expectedGroupRevision": 113' in s and 'row["revision"] != 86' in s
