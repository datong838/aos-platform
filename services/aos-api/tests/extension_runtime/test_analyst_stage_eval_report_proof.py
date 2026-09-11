from datetime import UTC, datetime, timedelta
import importlib
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[4]
BACKEND=ROOT/"bundles/solutions/ecommerce-growth/backend"
NOW=datetime(2026,9,12,5,0,tzinfo=UTC)
HASH="a"*64

@pytest.fixture
def package(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return (importlib.import_module("ecommerce_growth.ecommerce_analyst_authority_contracts"),
        importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_decision"),
        importlib.import_module("ecommerce_growth.ecommerce_analyst_stage_eval_report"))

def values(package):
    c,d,m=package
    tenant=c.TenantContext(orgId="org-org",projectId="dev-project")
    artifact=m.EvalSubjectArtifactRef(resourceId="artifact",contentHash=HASH)
    attempt=d.EvalStageAttemptRef(runId="run",stepKey="portrait",stepRunId="step",attempt=1,inputHash="b"*64)
    contract=m.EvalContractRevisionRef(resourceId="contract",revision=1,contentHash=HASH)
    policy=m.EvalGatePolicyRef(resourceId="policy",revision=1,contentHash=HASH)
    proof=m.StageEvalReportProof(tenant=tenant,reportRef=c.AnalystExactRef(resourceType="EvalReportRevision",resourceId="report",revision=1,contentHash=HASH),
        evalContractRef=contract,subjectArtifactRef=artifact,stageAttemptRef=attempt,gatePolicyRef=policy,
        evidenceCutoffAt=NOW-timedelta(minutes=1),gatePassed=True,createdAt=NOW)
    return m,proof,dict(tenant=tenant,artifact_ref=artifact,stage_attempt_ref=attempt,eval_contract_ref=contract,
        gate_policy_ref=policy,cutoff_at=NOW-timedelta(minutes=1),now=NOW)

def test_exact_passed_proof_matches(package):
    m,proof,args=values(package)
    assert m.require_stage_eval_report_inputs(proof=proof,**args) is None

@pytest.mark.parametrize("fault",["tenant","artifact","attempt","contract","policy","cutoff","future"])
def test_input_drift_fails_closed(package,fault):
    c,_,_=package;m,proof,args=values(package)
    if fault=="tenant":args["tenant"]=c.TenantContext(orgId="dev-org",projectId="dev-project")
    elif fault=="cutoff":args["cutoff_at"]-=timedelta(seconds=1)
    elif fault=="future":args["now"]-=timedelta(seconds=1)
    else:
        key={"artifact":"artifact_ref","attempt":"stage_attempt_ref","contract":"eval_contract_ref","policy":"gate_policy_ref"}[fault]
        field="input_hash" if fault=="attempt" else "content_hash"
        args[key]=args[key].model_copy(update={field:"c"*64})
    with pytest.raises(ValueError,match="inputs drifted"):m.require_stage_eval_report_inputs(proof=proof,**args)

@pytest.mark.parametrize("fault",["report","failed","naive_created","naive_cutoff","late_cutoff"])
def test_invalid_proof_fails_closed(package,fault):
    c,_,m=package;_,proof,_=values(package);body=proof.model_dump(mode="python",by_alias=True)
    if fault=="report":body["reportRef"]=c.AnalystExactRef(resourceType="Artifact",resourceId="report",revision=1,contentHash=HASH)
    elif fault=="failed":body["gatePassed"]=False
    elif fault=="naive_created":body["createdAt"]=NOW.replace(tzinfo=None)
    elif fault=="naive_cutoff":body["evidenceCutoffAt"]=(NOW-timedelta(minutes=1)).replace(tzinfo=None)
    else:body["evidenceCutoffAt"]=NOW+timedelta(seconds=1)
    with pytest.raises(ValueError,match="valid passed exact"):m.StageEvalReportProof.model_validate(body)

def test_boolean_revisions_rejected(package):
    _,_,m=package
    with pytest.raises(ValueError):m.EvalContractRevisionRef(resourceId="c",revision=True,contentHash=HASH)

def test_standalone_import_never_loads_platform_modules():
    program='''
import sys
class Deny:
 def find_spec(self,fullname,path=None,target=None):
  if fullname=="aos_api" or fullname.startswith("aos_api."): raise AssertionError(fullname)
sys.meta_path.insert(0,Deny());sys.path.insert(0,sys.argv[1])
from ecommerce_growth.ecommerce_analyst_stage_eval_report import StageEvalReportProof
assert StageEvalReportProof and not any(x.startswith("aos_api") for x in sys.modules)
'''
    subprocess.run([sys.executable,"-I","-c",program,str(BACKEND)],check=True,capture_output=True,text=True)
