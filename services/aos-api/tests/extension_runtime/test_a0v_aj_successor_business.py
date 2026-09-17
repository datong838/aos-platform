"""AJ registration binds exact AI detach."""
import importlib.util
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_aj_successor_business.py"
SPEC=importlib.util.spec_from_file_location("a0v_aj_successor_business",PATH);successor=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(successor)
def test_exact():
 assert successor.AJ_ID=="cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
 assert successor.AI_ID=="59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
 assert successor.DETACH=="5256f0d1-292c-4890-b127-3c17086c59e4"
 s=PATH.read_text();assert '"expectedGroupRevision": 107' in s and 'row["revision"] != 80' in s
