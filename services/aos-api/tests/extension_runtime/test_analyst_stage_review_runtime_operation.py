import importlib
from pathlib import Path
import pytest

from test_analyst_stage_review_command_identity import package_item
from test_analyst_stage_review_runtime_rule import values as runtime_values, observation
from test_analyst_stage_eval_report_proof import values as proof_values

ROOT=Path(__file__).resolve().parents[4];BACKEND=ROOT/"bundles/solutions/ecommerce-growth/backend"

@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    runtime=importlib.import_module("ecommerce_growth")
    c=importlib.import_module("ecommerce_growth.ecommerce_analyst_authority_contracts")
    d=importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_decision")
    command=importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_review_command")
    return runtime,(c,d,command)

def call(runtime,payload):return runtime.handle("ecommerce_growth_review_advance",payload,object())

def test_command_and_slot_messages(package):
    runtime,parts=package;item=package_item(parts)
    body={"kind":"validate_command_identity","tenant":item.tenant.model_dump(mode="json",by_alias=True),
        "item":item.model_dump(mode="json",by_alias=True),"actor":item.created_by,"key":"review-1","expectedVersion":0}
    assert call(runtime,body)["decisionRef"]["resourceId"]==item.decision_id
    slot={"kind":"validate_review_slot","stage":"portrait","actor":item.created_by,"slotId":"analyst.portrait.review",
        "responsibilityType":"independent_review","requiredCapabilityIds":[],"returnStage":"portrait",
        "assignee":item.reviewer.model_dump(mode="json",by_alias=True),"assigneeResolutionReceiptId":"resolution-1"}
    assert call(runtime,slot)["assignee"]["resourceId"]==item.created_by

def test_runtime_and_eval_messages(package):
    runtime,parts=package;c,d,_=parts
    class MP:
        def syspath_prepend(self,_):pass
    runtime_pkg=(c,d,importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_review_runtime"))
    values=runtime_values(runtime_pkg);obs=observation(values)
    body={"kind":"validate_runtime","taskRunId":values["task_run_id"],"planRef":values["plan_ref"].model_dump(mode="json",by_alias=True),
        "stage":values["stage"],"stageAttemptRef":values["stage_attempt_ref"].model_dump(mode="json",by_alias=True),
        "subjectRef":values["subject_ref"].model_dump(mode="json",by_alias=True),"observationPayload":obs}
    assert call(runtime,body)["subjectRef"]["resourceId"]=="subject-1"
    eval_pkg=(c,d,importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_eval_report"))
    m,proof,args=proof_values(eval_pkg)
    e={"kind":"validate_eval_proof","proof":proof.model_dump(mode="json",by_alias=True),"tenant":args["tenant"].model_dump(mode="json",by_alias=True),
        "artifactRef":args["artifact_ref"].model_dump(mode="json",by_alias=True),"stageAttemptRef":args["stage_attempt_ref"].model_dump(mode="json",by_alias=True),
        "evalContractRef":args["eval_contract_ref"].model_dump(mode="json",by_alias=True),"gatePolicyRef":args["gate_policy_ref"].model_dump(mode="json",by_alias=True),
        "cutoffAt":args["cutoff_at"].isoformat(),"now":args["now"].isoformat()}
    assert call(runtime,e)["reportRef"]["resourceId"]=="report"

@pytest.mark.parametrize("payload",[{}, {"kind":"unknown"}, {"kind":"validate_runtime","orgId":"org-org"}])
def test_unknown_or_inexact_messages_rejected(package,payload):
    with pytest.raises((ValueError,PermissionError)):call(package[0],payload)
