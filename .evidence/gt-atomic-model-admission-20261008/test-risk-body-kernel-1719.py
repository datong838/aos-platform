import json
from pathlib import Path
from aos_api import aip_physical_capacity_occupation_authority as api

def test_original_risk_body_shared_and_sql_exact(monkeypatch):
    before=json.loads(Path(__file__).with_name("risk-body-kernel-beforeimage-1719.json").read_text())
    for n, statements in before.items(): assert list(getattr(api,n)())==statements
    kernel=api.shared_parent_original_risk_body_sql()
    statements=api.occupation_plan_risk_statements()
    producer=next(x for x in statements if x.startswith("CREATE FUNCTION "+api.PLAN_RISK.split("(")[0]+"("))
    assert producer.count(kernel)==1
    monkeypatch.setattr(api,"shared_parent_original_risk_body_sql",lambda:"--not executed")
    assert api.occupation_plan_risk_statements()==tuple(x.replace(kernel,"--not executed") if x==producer else x for x in statements)
