import json
from pathlib import Path
import pytest
from aos_api import aip_physical_capacity_occupation_authority as api

def test_all_original_generated_sql_exact():
    original=json.loads(Path(__file__).with_name("shared-description-kernel-beforeimage-1718.json").read_text())["generators"]
    for name, statements in original.items():
        assert list(getattr(api,name)())==statements,name

def test_original_producer_consumes_shared_complete_kernel(monkeypatch):
    kernel=api.shared_parent_description_validation_sql()
    before=api.occupation_shared_risk_description_statements()
    producer=next(s for s in before if s.startswith("CREATE FUNCTION "))
    assert producer.count(kernel)==1
    marker="\n-- test-owned not executed\n"
    monkeypatch.setattr(api,"shared_parent_description_validation_sql",lambda:marker)
    assert api.occupation_shared_risk_description_statements()==tuple(s.replace(kernel,marker) if s==producer else s for s in before)

def test_complete_original_validation_and_no_mutation():
    kernel=api.shared_parent_description_validation_sql()
    for gate in ["CAPACITY_SHARED_DESCRIPTION_ORIGINAL_REQUIRED","CAPACITY_SHARED_DESCRIPTION_PARENT_REQUIRED","CAPACITY_SHARED_DESCRIPTION_CASE_REQUIRED","CAPACITY_SHARED_DESCRIPTION_LEG_REQUIRED"]:
        assert gate in kernel
    for binding in ["caseSetHash","originalFacts","approvalEventId","parentHoldRef","allocationUpperBoundMinor","accountCandidateRef","providerRefs","expectedArtifact"]:
        assert binding in kernel
    assert "INSERT INTO" not in kernel and "UPDATE " not in kernel and "COMMIT" not in kernel

@pytest.mark.parametrize("override",["schema",{},True,None])
def test_no_caller_override(override):
    with pytest.raises(TypeError): api.shared_parent_description_validation_sql(override)
