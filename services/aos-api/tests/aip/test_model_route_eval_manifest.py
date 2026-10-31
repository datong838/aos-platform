"""Fresh descriptive fixtures only; no historical approvals/journals are reused."""
from copy import deepcopy
from datetime import timedelta
import json

import pytest

from aos_api.aip_budget_reservation_contracts import ReserveBudgetRequest, BudgetReservationRevision
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_execution_contracts import ModelEvalTargetJudgeExecutionManifest, ModelEvalTargetJudgeSharedRiskManifest
from aos_api.aip_model_eval_judge_authorization import ModelJudgeRuleDefinition
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_eval_pack_registry import compute_eval_suite_hash, AipEvalPackRegistry
from aos_api.aip_model_route_eval_manifest import (
    RouteEvalApplication, RouteEvalBudgetBinding, compile_eval_execution_manifest,
    eval_context_binding_hash, route_eval_call_key, route_eval_approval_payload,
    validate_route_eval_application,
)
from test_model_route_eval_context_reader import SQLSnapshot, read
from test_model_route_eval_subject_binding import TENANT, NOW, model, candidate, exact_ref


def dump(x): return x.model_dump(mode='json', by_alias=True)
def bref(kind, name):
    return dict(resourceType=kind, resourceId=name, revision=1, contentHash='sha256:' + 'b'*64)


def rule_inputs(selected):
    artifact=lambda n:dict(relativePath=n+'.json',artifactRef='bundle://fixture/'+n+'.json',digest='sha256:'+'a'*64,size=1,mediaType='application/json')
    source=dict(publisher='fixture',bundleId='fixture',version='1.0.0',contentHash='sha256:'+'b'*64,
        ruleArtifact=artifact('rule'),templateArtifact=artifact('template'),implementationArtifact=artifact('implementation'))
    rule=ModelJudgeRuleDefinition(schemaVersion='aos.model-judge-rule/v1',judgeId='judge',revision=1,
        modelRef=exact_ref(selected,'RegisteredModelRevision',selected.registered_model_id),templateVersion='1.0.0',implementationVersion='1.0.0',
        templateDigest='sha256:'+'a'*64,implementationDigest='sha256:'+'a'*64,inputProtocol='aos.model-eval-judge-input/v1',outputProtocol='aos.model-judge-verdict/v1')
    return rule,source


def context(*, route=True, outside_judge=False):
    conn = SQLSnapshot(route=route)
    judge_model = (model('outside-judge') if outside_judge else conn.models[-1]) if route else model('judge-model', lifecycle='draft')
    conn.run['judge_ref'] = {**conn.run['judge_ref'], 'modelRoute': dict(
        assetType='registered_model', assetId=judge_model.registered_model_id,
        revision=str(judge_model.revision), contentHash=judge_model.content_hash)}
    conn.run['judge_ref']['contentHash']=canonical_hash(dump(rule_inputs(judge_model)[0]))
    conn.suite['judge_ref'] = deepcopy(conn.run['judge_ref'])
    reseal_context(conn)
    return conn, judge_model


def reseal_context(conn):
    suite = AipEvalPackRegistry._suite_from_row(conn.suite)
    h = compute_eval_suite_hash(suite)
    conn.suite['content_hash'] = h; conn.run['suite_hash'] = h
    conn.contract['suite_ref']['contentHash'] = h
    from aos_api.aip_production_contracts import CreateEvalContractRequest
    request = CreateEvalContractRequest.model_validate({n: conn.contract[n] for n in CreateEvalContractRequest.model_fields})
    conn.contract['content_hash'] = canonical_hash(dump(request))
    conn.run['eval_contract_ref']['contentHash'] = conn.contract['content_hash']


def route_inputs(*,outside_judge=False):
    conn, judge_model = context(outside_judge=outside_judge)
    raw = read(conn); h = eval_context_binding_hash(raw)
    recipes = []
    for purpose, selected in [('target', conn.models[0]), ('judge', judge_model)]:
        recipes.append(dict(caseId='case', purpose=purpose, modelRef=dump(exact_ref(selected, 'RegisteredModelRevision', selected.registered_model_id)),
            providerRef=dump(selected.provider), priceRef=dump(selected.price_snapshot_ref),
            quotaPolicyRef=dump(selected.quota_policy_ref), budgetPolicyRef=dump(selected.budget_policy_ref),
            taskBudgetRef=bref('BudgetRevision', 'budget'), sourceRef=dict(assetType='ProviderCapacitySourceRevision', assetId='source-'+purpose, revision=1, contentHash='c'*64),
            physicalAccountRef=dict(assetType='ProviderPhysicalAccountCandidateRevision', assetId='account-'+purpose, revision=1, contentHash='d'*64),
            identityId=purpose+'-executor', identityKeyHash=('e' if purpose=='target' else 'f')*64,
            inputHash=conn.suite['cases'][0]['inputArtifact']['contentHash'], expectedHash=None,
            wireInputHash='c'*64 if purpose=='target' else None,
            targetCallKey=None if purpose=='target' else route_eval_call_key('fresh-execution',h,'case','target'),
            inputProtocol='case-artifact-wire/v1' if purpose=='target' else 'aos.model-eval-judge-input/v1',
            maxOutputTokens=128,upperBoundMinor=3, attempt=1))
    rule,rule_source=rule_inputs(judge_model)
    app = RouteEvalApplication(tenant=TENANT, executionId='fresh-execution', taskRef=bref('Task', 'task'), judgeModel=judge_model,
        judgeRule=rule,judgeRuleSource=rule_source,
        contextBindingHash=h, expiresAt=NOW+timedelta(hours=1), upperBoundMinor=6,
        calls=recipes, executionAllowed=False)
    bindings = []
    for recipe in app.calls:
        role = recipe.purpose
        request = ReserveBudgetRequest(operationId='aip_route_eval_'+role+'_call',
            invocationKey=route_eval_call_key(app.execution_id, h, recipe.case_id, role), taskRef=app.task_ref,
            policyRef=recipe.task_budget_ref, pricingRef=dict(resourceType='ModelPriceSnapshotRevision',
                resourceId=recipe.price_ref.asset_id, revision=recipe.price_ref.revision, contentHash='sha256:'+recipe.price_ref.content_hash),
            approvalRef=bref('ActionApprovalEvent', role+'-approval'), upperBoundMinor=3)
        reservation = BudgetReservationRevision(tenant=TENANT, invocationRef=bref('CapabilityInvocationRevision', role+'-invocation'),
            reservationRef=bref('BudgetReservationRevision', role+'-reservation'), operationId=request.operation_id,
            invocationKey=request.invocation_key, taskRef=request.task_ref, policyRef=request.policy_ref, pricingRef=request.pricing_ref,
            approvalRef=request.approval_ref, state='held', currency='CNY', upperBoundMinor=3,
            buckets=[dict(kind=k, accountId='budget-'+k, periodStart=NOW-timedelta(days=1), periodEnd=NOW+timedelta(days=1),
                currency='CNY', limitMinor=100, heldMinor=6, submittedMinor=0, settledMinor=0, unknownMinor=0) for k in ['task','daily','pilot']],
            requestHash=request.request_hash(), createdAt=NOW, updatedAt=NOW)
        bindings.append(RouteEvalBudgetBinding(callKey=request.invocation_key, request=request, reservation=reservation))
    return raw, app, bindings


def model_inputs(version):
    conn, judge = context(route=False)
    source = conn.source
    # Entirely fresh structural Model requests/rule/application facts.
    target_req = ModelEvalRequestCreate(tenant=TENANT, sourceRef=candidate(source).source_ref, targetRef=candidate(source).target_ref,
        expectedHeadVersion=7, evalContractRef=dict(assetType='EvalContractRevision', assetId='contract', revision=1, contentHash='a'*64),
        suiteRef=dict(assetType='EvalSuiteRevision', assetId='suite', revision=1, contentHash='a'*64),
        providerRef=source.provider, priceRef=source.price_snapshot_ref, quotaPolicyRef=source.quota_policy_ref,
        budgetPolicyRef=source.budget_policy_ref, upperBoundMinor=10, expiresAt=NOW+timedelta(hours=1))
    judge_req = target_req.model_copy(update={'source_ref':candidate(judge).source_ref,'target_ref':candidate(judge).target_ref})
    artifact = lambda n: dict(relativePath=n+'.json', artifactRef='bundle://fixture/'+n+'.json', digest='sha256:'+'a'*64, size=1, mediaType='application/json')
    rule_source = dict(publisher='fixture', bundleId='fixture', version='1.0.0', contentHash='sha256:'+'b'*64,
        ruleArtifact=artifact('rule'), templateArtifact=artifact('template'), implementationArtifact=artifact('implementation'))
    rule = ModelJudgeRuleDefinition(schemaVersion='aos.model-judge-rule/v1', judgeId='judge', revision=1,
        modelRef=judge_req.source_ref, templateVersion='1.0.0', implementationVersion='1.0.0', templateDigest='sha256:'+'a'*64,
        implementationDigest='sha256:'+'a'*64, inputProtocol='aos.model-eval-judge-input/v1', outputProtocol='aos.model-judge-verdict/v1')
    conn.run['judge_ref']['contentHash'] = canonical_hash(dump(rule)); conn.suite['judge_ref']=deepcopy(conn.run['judge_ref'])
    reseal_context(conn)
    target_req = target_req.model_copy(update={'eval_contract_ref':target_req.eval_contract_ref.model_copy(update={'content_hash':conn.contract['content_hash']}),
        'suite_ref':target_req.suite_ref.model_copy(update={'content_hash':conn.suite['content_hash']})})
    def application(req, name):
        return dict(requestId=name, requestHash=canonical_hash(dump(req)), request=dump(req),
            approvalEventId=name+'-approval', proposalId=name+'-proposal', proposalHash='a'*64)
    t, j = application(target_req,'target-app'), application(judge_req,'judge-governance')
    raw_request = dict(schemaVersion='aos.model-judge-call-request/v2',tenant=TENANT,purpose='model-judge-call',executionAllowed=False,
        createdBy='synthetic-not-human',targetApplication=t,judgeGovernanceApplication=j,suiteRef=dump(target_req.suite_ref),
        evalContractRef=dump(target_req.eval_contract_ref),judgeRef=conn.run['judge_ref'],cases=conn.suite['cases'],
        caseSetHash=canonical_hash(conn.suite['cases']),currency='CNY',upperBoundMinor=10,expiresAt=(NOW+timedelta(hours=1)).isoformat(),
        ruleFacts=dict(source=rule_source,rule=dump(rule),rootRevision=None,validUntil=None,ruleHash=canonical_hash(dump(rule)),
            signatureFingerprint='sha256:'+'c'*64,releaseEvidenceRevision='sha256:'+'d'*64,approvalAllowed=False,executionAllowed=False))
    parents, legs = [], []
    for role, req in [('target',target_req),('judge',judge_req)]:
        approval = bref('ActionApprovalEvent', 'target-app-approval' if role=='target' else 'new-judge-approval')
        hold = bref('ModelEvalBudgetReservation' if role=='target' else 'ModelJudgeBudgetReservation',role+'-hold')
        parent = dict(parentHoldRef=hold,requestId='target-app' if role=='target' else 'new-judge-request',
            requestHash=t['requestHash'] if role=='target' else canonical_hash(raw_request),approvalRef=approval,
            budgetPolicyRef=dump(req.budget_policy_ref),priceRef=dump(req.price_ref),currency='CNY',upperBoundMinor=10)
        if role=='judge':parent.update(schemaVersion='aos.model-judge-parent-budget/v1',purpose='model-judge-call',tenant=TENANT,executionAllowed=False)
        parents.append(parent)
        leg=dict(tenant=TENANT,purpose=role,modelRef=dump(req.source_ref),providerRef=dump(req.provider_ref),priceRef=dump(req.price_ref),
            quotaPolicyRef=dump(req.quota_policy_ref),budgetPolicyRef=dump(req.budget_policy_ref),sourceRef=dict(assetType='ProviderCapacitySourceRevision',assetId=role+'-source',revision=1,contentHash='a'*64),
            physicalAccountRef=dict(assetType='ProviderPhysicalAccountCandidateRevision',assetId=role+'-account',revision=1,contentHash='a'*64),
            approvalRef=approval,budgetHoldRef=hold,jointReceiptRef=bref('ModelEvalJointAdmissionReceipt',role+'-joint'),
            intentRef=bref('ModelEvalExecutionIntent',role+'-intent'),identityId=role+'-executor',identityKeyHash=('e' if role=='target' else 'f')*64,attempt=1)
        if version==2:leg.update(budgetAllocationRef=bref('ModelEvalBudgetAllocation',role+'-allocation'),allocationUpperBoundMinor=3)
        legs.append(leg)
    case=dict(caseId='case',inputHash=conn.suite['cases'][0]['inputArtifact']['contentHash'],expectedHash=None,target=legs[0],judge=legs[1])
    cls=ModelEvalTargetJudgeExecutionManifest if version==2 else ModelEvalTargetJudgeSharedRiskManifest
    plan=cls(schemaVersion='aos.model-eval-target-judge-manifest/v2' if version==2 else 'aos.model-eval-target-judge-shared-risk-manifest/v3',
        tenant=TENANT,executionId='fresh-model',judgeRequestId='new-judge-request',judgeRequestHash=canonical_hash(raw_request),
        judgeRequest=raw_request,targetParentBudget=parents[0],judgeParentBudget=parents[1],cases=[case],
        caseSetHash=canonical_hash([dict(caseId='case',inputHash=case['inputHash'],expectedHash=None)]),executionAllowed=False)
    return read(conn), plan


def test_route_complete_manifest_is_nonexecuting_and_approval_recipe_is_acyclic():
    raw, app, bindings = route_inputs()
    result = compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)
    body=json.loads(result.split(b'\n',1)[1]);assert body['executionAllowed'] is False
    payload=route_eval_approval_payload(app,app.calls[0])
    assert payload['applicationHash']==canonical_hash(dump(app)) and payload['budgetUpperBoundMinor']==3
    assert 'approvalRef' not in dump(app)['calls'][0] and 'reservationRef' not in dump(app)['calls'][0]


def test_independent_judge_need_not_be_a_target_route_candidate():
    raw,app,bindings=route_inputs(outside_judge=True)
    result=compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)
    body=json.loads(result.split(b'\n',1)[1])
    assert body['routeApplication']['judgeModel']['registeredModelId']=='outside-judge'
    assert 'outside-judge' not in [m['registeredModelId'] for m in body['context']['subject']['models']]


@pytest.mark.parametrize('version',[2,3])
def test_both_original_model_plan_versions_are_preserved(version):
    raw, plan = model_inputs(version)
    result=compile_eval_execution_manifest(raw,execution_id=plan.execution_id,checked_at=NOW,model_plan=plan)
    assert json.loads(result.split(b'\n',1)[1])['modelPlan']==dump(plan)


@pytest.mark.parametrize('fault',['missing','duplicate_hold','wrong_key','wrong_price','wrong_budget','cap','expired',
    'same_identity','same_key','zero_attempt','extra','purpose','wrong_model','judge','context','wire_bool','submitted'])
def test_route_incomplete_or_cross_purpose_facts_are_rejected(fault):
    raw, app, bindings = route_inputs()
    if fault=='missing':bindings.pop()
    elif fault=='duplicate_hold':bindings[1]=bindings[1].model_copy(update={'reservation':bindings[1].reservation.model_copy(update={'reservation_ref':bindings[0].reservation.reservation_ref})})
    elif fault=='wrong_key':bindings[0]=bindings[0].model_copy(update={'call_key':'other'})
    elif fault=='wrong_price':bindings[0]=bindings[0].model_copy(update={'request':bindings[0].request.model_copy(update={'pricing_ref':bindings[1].request.pricing_ref.model_copy(update={'resource_id':'other'})})})
    elif fault=='wrong_budget':bindings[0]=bindings[0].model_copy(update={'request':bindings[0].request.model_copy(update={'policy_ref':bindings[0].request.policy_ref.model_copy(update={'resource_id':'other'})})})
    elif fault=='cap':app=app.model_copy(update={'upper_bound_minor':5})
    elif fault=='expired':app=app.model_copy(update={'expires_at':NOW})
    elif fault=='same_identity':app.calls[1]=app.calls[1].model_copy(update={'identity_id':app.calls[0].identity_id})
    elif fault=='same_key':app.calls[1]=app.calls[1].model_copy(update={'identity_key_hash':app.calls[0].identity_key_hash})
    elif fault=='zero_attempt':app.calls[0]=app.calls[0].model_copy(update={'attempt':0})
    elif fault=='extra':app=app.model_copy(update={'dispatchAllowed':True})
    elif fault=='purpose':app=app.model_copy(update={'purpose':'quality-eval'})
    elif fault=='wrong_model':app.calls[0]=app.calls[0].model_copy(update={'model_ref':app.calls[1].model_ref.model_copy(update={'asset_id':'outside-route'})})
    elif fault=='judge':app.calls[1]=app.calls[1].model_copy(update={'model_ref':app.calls[0].model_ref})
    elif fault=='context':app=app.model_copy(update={'context_binding_hash':'0'*64})
    elif fault=='wire_bool':app.calls[0]=app.calls[0].model_copy(update={'wire_input_hash':True})
    else:bindings[0]=bindings[0].model_copy(update={'reservation':bindings[0].reservation.model_copy(update={'state':'submitted'})})
    with pytest.raises(ValueError):compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)


def test_clock_changes_do_not_create_approval_hash_cycles_but_remain_origin_metadata():
    raw, app, bindings=route_inputs();body=json.loads(raw.split(b'\n',1)[1]);body['snapshotReadAt']=(NOW+timedelta(seconds=1)).isoformat()
    later=raw.split(b'\n',1)[0]+b'\n'+json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    assert eval_context_binding_hash(raw)==eval_context_binding_hash(later)
    result=compile_eval_execution_manifest(later,execution_id=app.execution_id,checked_at=NOW+timedelta(seconds=1),route_application=app,route_budget_bindings=bindings)
    assert json.loads(result.split(b'\n',1)[1])['context']['snapshotReadAt']==body['snapshotReadAt']
    with pytest.raises(ValueError):compile_eval_execution_manifest(later,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)


def context_bytes(body):
    return b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()


@pytest.mark.parametrize('fault',['null_subject','list_subject','missing_candidate','null_candidate','missing_source_ref','null_source_ref','models_not_list'])
def test_malformed_context_subject_is_an_explicit_input_rejection(fault):
    raw,_,_=route_inputs();body=json.loads(raw.split(b'\n',1)[1])
    if fault=='null_subject':body['subject']=None
    elif fault=='list_subject':body['subject']=[]
    elif fault=='missing_candidate':body['subject'].pop('candidate')
    elif fault=='null_candidate':body['subject']['candidate']=None
    elif fault=='missing_source_ref':body['subject']['candidate'].pop('sourceRef')
    elif fault=='null_source_ref':body['subject']['candidate']['sourceRef']=None
    else:body['subject']['models']={}
    with pytest.raises(ValueError):eval_context_binding_hash(context_bytes(body))


@pytest.mark.parametrize('fault',['duplicate','whitespace','nonfinite','extra'])
def test_context_requires_exact_original_canonical_json(fault):
    raw,_,_=route_inputs()
    if fault=='duplicate':bad=raw.replace(b'"executionAllowed":false',b'"executionAllowed":false,"executionAllowed":false',1)
    elif fault=='whitespace':bad=raw.replace(b'\n{',b'\n{ ',1)
    elif fault=='nonfinite':bad=raw.replace(b'"executionAllowed":false',b'"executionAllowed":NaN',1)
    else:
        body=json.loads(raw.split(b'\n',1)[1]);body['executionToken']='invented';bad=context_bytes(body)
    with pytest.raises(ValueError):eval_context_binding_hash(bad)


@pytest.mark.parametrize('fault',['future_judge_wire','wrong_parent','wrong_rule','too_many_tokens','copied_extra','alias_collision'])
def test_route_judge_derivation_and_original_aliases_are_bound(fault):
    raw,app,bindings=route_inputs()
    if fault=='future_judge_wire':app.calls[1]=app.calls[1].model_copy(update={'wire_input_hash':'c'*64})
    elif fault=='wrong_parent':app.calls[1]=app.calls[1].model_copy(update={'target_call_key':'another-case-target'})
    elif fault=='wrong_rule':app=app.model_copy(update={'judge_rule':app.judge_rule.model_copy(update={'judge_id':'other'})})
    elif fault=='too_many_tokens':app.calls[0]=app.calls[0].model_copy(update={'max_output_tokens':app.judge_model.context_window+1})
    elif fault=='copied_extra':app=app.model_copy(update={'judge_rule_source':app.judge_rule_source.model_copy(update={'rule_artifact':app.judge_rule_source.rule_artifact.model_copy(update={'grant':'invented'})})})
    else:app=app.model_copy(update={'contextBindingHash':'0'*64})
    with pytest.raises(ValueError):compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)


@pytest.mark.parametrize('version',[2,3])
@pytest.mark.parametrize('fault',['bool_revision','string_revision','same_identity','same_key'])
def test_original_model_plans_keep_native_refs_and_independent_identities(version,fault):
    raw,plan=model_inputs(version)
    if fault.endswith('revision'):
        plan.cases[0].target.model_ref=plan.cases[0].target.model_ref.model_copy(update={'revision':True if fault=='bool_revision' else '1'})
    else:
        field='identity_id' if fault=='same_identity' else 'identity_key_hash'
        plan.cases[0].judge=plan.cases[0].judge.model_copy(update={field:getattr(plan.cases[0].target,field)})
    with pytest.raises(ValueError):compile_eval_execution_manifest(raw,execution_id=plan.execution_id,checked_at=NOW,model_plan=plan)


@pytest.mark.parametrize('status',['unknown','succeeded','failed','cancelled'])
def test_terminal_or_unknown_origin_run_cannot_create_new_execution_intent(status):
    raw,app,bindings=route_inputs();body=json.loads(raw.split(b'\n',1)[1]);body['run']['status']=status
    with pytest.raises(ValueError):compile_eval_execution_manifest(context_bytes(body),execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)


@pytest.mark.parametrize('fault',['bool_held','string_held','bool_limit','naive_start','naive_end','reversed_clock'])
def test_route_original_budget_numbers_and_clocks_are_not_normalized(fault):
    raw,app,bindings=route_inputs();res=bindings[0].reservation
    if fault=='reversed_clock':res=res.model_copy(update={'created_at':NOW,'updated_at':NOW-timedelta(seconds=1)})
    else:
        buckets=list(res.buckets);bucket=buckets[0]
        if fault=='bool_held':change={'held_minor':True}
        elif fault=='string_held':change={'held_minor':'6'}
        elif fault=='bool_limit':change={'limit_minor':True}
        elif fault=='naive_start':change={'period_start':bucket.period_start.replace(tzinfo=None)}
        else:change={'period_end':bucket.period_end.replace(tzinfo=None)}
        buckets[0]=bucket.model_copy(update=change);res=res.model_copy(update={'buckets':tuple(buckets)})
    bindings[0]=bindings[0].model_copy(update={'reservation':res})
    with pytest.raises(ValueError):compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)


@pytest.mark.parametrize('outside_judge',[False,True])
def test_preapproval_validates_whole_application_without_budget_or_approval_inputs(outside_judge):
    raw,app,_=route_inputs(outside_judge=outside_judge)
    checked=validate_route_eval_application(raw,application=app,checked_at=NOW)
    assert type(checked) is RouteEvalApplication and dump(checked)==dump(app)
    assert checked.execution_allowed is False
    checked.calls[0].identity_id='changed-returned-description'
    checked.judge_model.capabilities.append('changed-returned-model')
    assert app.calls[0].identity_id=='target-executor'
    assert 'changed-returned-model' not in app.judge_model.capabilities


@pytest.mark.parametrize('fault',[
    'model_context','terminal_run','future_snapshot','naive_clock','expired','wrong_context',
    'missing_case','order','duplicate','tenant','outside_target','wrong_judge','wrong_rule',
    'provider','price','quota','budget','input','expected','same_identity','same_key',
    'wrong_target_key','extra','execution_true','bool_revision','cap','future_judge_wire',
])
def test_preapproval_rejects_incomplete_or_drifted_material_without_holds(fault):
    raw,app,_=route_inputs();at=NOW
    if fault=='model_context':raw,_=model_inputs(2)
    elif fault in {'terminal_run','future_snapshot'}:
        body=json.loads(raw.split(b'\n',1)[1])
        if fault=='terminal_run':body['run']['status']='succeeded'
        else:body['snapshotReadAt']=(NOW+timedelta(seconds=1)).isoformat()
        raw=context_bytes(body)
        app=app.model_copy(update={'context_binding_hash':eval_context_binding_hash(raw)})
    elif fault=='naive_clock':at=NOW.replace(tzinfo=None)
    elif fault=='expired':app=app.model_copy(update={'expires_at':NOW})
    elif fault=='wrong_context':app=app.model_copy(update={'context_binding_hash':'0'*64})
    elif fault=='missing_case':app=app.model_copy(update={'calls':app.calls[:1]})
    elif fault=='order':app=app.model_copy(update={'calls':list(reversed(app.calls))})
    elif fault=='duplicate':app=app.model_copy(update={'calls':[app.calls[0],app.calls[0]]})
    elif fault=='tenant':app=app.model_copy(update={'tenant':app.tenant.model_copy(update={'org_id':'dev-org'})})
    elif fault=='wrong_rule':app=app.model_copy(update={'judge_rule':app.judge_rule.model_copy(update={'judge_id':'other'})})
    elif fault=='extra':app=app.model_copy(update={'approvalRef':bref('ActionApprovalEvent','invented')})
    elif fault=='execution_true':app=app.model_copy(update={'execution_allowed':True})
    elif fault=='cap':app=app.model_copy(update={'upper_bound_minor':5})
    else:
        i=1 if fault in {'wrong_judge','same_identity','same_key','wrong_target_key','future_judge_wire'} else 0
        c=app.calls[i]
        if fault=='outside_target':change={'model_ref':c.model_ref.model_copy(update={'asset_id':'outside-route'})}
        elif fault=='wrong_judge':change={'model_ref':app.calls[0].model_ref}
        elif fault in {'provider','price','quota','budget'}:
            field={'provider':'provider_ref','price':'price_ref','quota':'quota_policy_ref','budget':'budget_policy_ref'}[fault]
            change={field:getattr(c,field).model_copy(update={'asset_id':'other'})}
        elif fault=='input':change={'input_hash':'0'*64}
        elif fault=='expected':change={'expected_hash':'0'*64}
        elif fault=='same_identity':change={'identity_id':app.calls[0].identity_id}
        elif fault=='same_key':change={'identity_key_hash':app.calls[0].identity_key_hash}
        elif fault=='wrong_target_key':change={'target_call_key':'other-target'}
        elif fault=='future_judge_wire':change={'wire_input_hash':'0'*64}
        else:change={'model_ref':c.model_ref.model_copy(update={'revision':True})}
        app.calls[i]=c.model_copy(update=change)
    with pytest.raises(ValueError):validate_route_eval_application(raw,application=app,checked_at=at)


def test_preapproval_rejects_zero_weight_target_with_self_consistent_original_context():
    from test_model_route_eval_subject_binding import inputs
    from aos_api.aip_production_contract_store import AipProductionContractStore
    conn,_=context();conn.source,conn.models,conn.policy=inputs(weighted=True)
    conn.claim=candidate(conn.source)
    target=dict(assetType='model_route',assetId=conn.claim.target_ref.asset_id,
        revision=str(conn.claim.target_ref.revision),contentHash=conn.claim.target_ref.content_hash)
    conn.run['target_ref']=target;conn.suite['target_ref']=target;conn.publication['target_ref']=target
    conn.contract['publication_ref']['contentHash']=canonical_hash(AipProductionContractStore._publication_snapshot(conn.publication))
    reseal_context(conn);raw=read(conn);h=eval_context_binding_hash(raw)
    _,app,_=route_inputs();app=app.model_copy(update={'context_binding_hash':h})
    app.calls[0]=app.calls[0].model_copy(update={'model_ref':exact_ref(conn.models[1],'RegisteredModelRevision',conn.models[1].registered_model_id)})
    app.calls[1]=app.calls[1].model_copy(update={'target_call_key':route_eval_call_key(app.execution_id,h,'case','target')})
    with pytest.raises(ValueError,match='zero weight'):
        validate_route_eval_application(raw,application=app,checked_at=NOW)


@pytest.mark.parametrize('kind,expected',[
    ('route','08481f79177c179294d06a2035fbefd1d1801e970ee109be9460c06a5c0e057c'),
    ('route_outside_judge','63cee3ddefffc2454b221b22809e18f2d79ccfed2487ade47341efddd07e88c2'),
    ('model2','e1d87b8a5cdabe5bbc642e92bbd95d66f97d31fd9ca3dcfc96073216a0976352'),
    ('model3','92062cdf62c0325ca8f663c18c5890c64e5e286cbae3d25ac2e9e1d79d86b587'),
])
def test_compiler_bytes_match_frozen_outputs_captured_before_preapproval_extraction(kind,expected):
    # Captured before source changes in route-preapproval-before-compiler-r1.json.
    from hashlib import sha256
    if kind.startswith('route'):
        raw,app,bindings=route_inputs(outside_judge=kind.endswith('outside_judge'))
        result=compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,
            route_application=app,route_budget_bindings=bindings)
    else:
        raw,plan=model_inputs(int(kind[-1]))
        result=compile_eval_execution_manifest(raw,execution_id=plan.execution_id,checked_at=NOW,model_plan=plan)
    assert sha256(result).hexdigest()==expected
