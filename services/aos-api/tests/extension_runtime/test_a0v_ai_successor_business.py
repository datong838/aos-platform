"""AI registration binds exact AH detach."""
import importlib.util
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ai_successor_business.py"
SPEC=importlib.util.spec_from_file_location("a0v_ai_successor_business",PATH);successor=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(successor)
def test_exact():
 assert successor.AI_ID=="59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
 assert successor.AH_ID=="9fe97ea8-275a-47d0-a0f1-d2064a8d62c6"
 assert successor.DETACH=="9b50a8eb-ed85-4c7b-9010-16e0bbea5875"
 s=PATH.read_text();assert '"expectedGroupRevision": 104' in s and 'row["revision"] != 77' in s
