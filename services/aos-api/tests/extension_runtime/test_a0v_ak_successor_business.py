"""AK registration binds exact AJ detach."""
import importlib.util
from pathlib import Path
PATH=Path(__file__).resolve().parents[4]/"scripts/a0v_ak_successor_business.py"
SPEC=importlib.util.spec_from_file_location("a0v_ak_successor_business",PATH);successor=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(successor)
def test_exact():
 assert successor.AK_ID=="038bd251-e2e3-415d-8706-955de809b4df"
 assert successor.AJ_ID=="cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
 assert successor.DETACH=="d66d9fea-c21f-47e0-a291-56d21d02989d"
 s=PATH.read_text();assert '"expectedGroupRevision": 110' in s and 'row["revision"] != 83' in s
