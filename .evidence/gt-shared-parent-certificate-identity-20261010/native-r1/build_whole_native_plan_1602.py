"""Descriptive refs around actual original request/parents; no Source proof."""
import json
from aos_api.aip_model_runtime_store import canonical_hash
from tests.aip.test_model_eval_execution_contracts import _whole_newjudge_body

def build(target,judge):
    body=_whole_newjudge_body()
    body.update(executionId='native-newJudge-'+judge.request_id,
        judgeRequestId=judge.request_id,judgeRequestHash=judge.request_hash,
        judgeRequest=judge.request,targetParentBudget=target.parent_limit.model_dump(mode='json',by_alias=True),
        judgeParentBudget=judge.parent_limit.model_dump(mode='json',by_alias=True))
    template=body['cases'][0];body['cases']=[]
    for i,original in enumerate(judge.request['cases']):
        case=json.loads(json.dumps(template));case.update(caseId=original['caseId'],
            inputHash=original['inputArtifact']['contentHash'],
            expectedHash=None if original.get('expectedArtifact') is None else original['expectedArtifact']['contentHash'])
        for purpose,app,parent in [('target',judge.request['targetApplication'],target.parent_limit),
                                   ('judge',judge.request['judgeGovernanceApplication'],judge.parent_limit)]:
            leg=case[purpose]
            for field in ('providerRef','priceRef','quotaPolicyRef','budgetPolicyRef'):
                leg[field]=json.loads(json.dumps(app['request'][field]))
            leg['modelRef']=json.loads(json.dumps(app['request']['sourceRef']))
            leg.update(budgetHoldRef=parent.parent_hold_ref.model_dump(mode='json',by_alias=True),
                approvalRef=parent.approval_ref.model_dump(mode='json',by_alias=True))
            for field in ('intentRef','budgetAllocationRef'):
                leg[field]['resourceId']+='-native-'+str(i)
        body['cases'].append(case)
    body['caseSetHash']=canonical_hash([{k:c[k] for k in ('caseId','inputHash','expectedHash')} for c in body['cases']])
    return body


def missing_parent_description(pending,approval_id):
    """Strict synthetic absent-parent description to test no-prefix-write denial."""
    from types import SimpleNamespace
    from uuid import uuid4
    from aos_api.aip_model_eval_execution_contracts import ModelEvalParentBudgetLimit,ModelJudgeParentBudgetLimit
    fixture=_whole_newjudge_body();raw=pending['request_json'];target=raw['targetApplication'];governance=raw['judgeGovernanceApplication']['request']
    tp=fixture['targetParentBudget'];jp=fixture['judgeParentBudget']
    tp.update(requestId=target['requestId'],requestHash=target['requestHash'],
        priceRef=target['request']['priceRef'],budgetPolicyRef=target['request']['budgetPolicyRef'],
        upperBoundMinor=target['request']['upperBoundMinor'])
    tp['approvalRef']['resourceId']=target['approvalEventId'];tp['parentHoldRef']['resourceId']=str(uuid4())
    jp.update(requestId=pending['request_id'],requestHash=pending['request_hash'],
        priceRef=governance['priceRef'],budgetPolicyRef=governance['budgetPolicyRef'],upperBoundMinor=raw['upperBoundMinor'])
    jp['approvalRef']['resourceId']=approval_id;jp['parentHoldRef']['resourceId']=str(uuid4())
    return build(SimpleNamespace(parent_limit=ModelEvalParentBudgetLimit.model_validate(tp)),
        SimpleNamespace(request_id=pending['request_id'],request_hash=pending['request_hash'],request=raw,
                        parent_limit=ModelJudgeParentBudgetLimit.model_validate(jp)))
