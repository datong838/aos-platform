"""Original Eval application on legal published Model; no Model quality grant."""
from datetime import datetime, UTC, timedelta
from pathlib import Path
from uuid import uuid4
import json
import pytest
from legal_model_prefix_for_application_r4 import create_prefix
from tests.aip.test_budget_cost_consumer_pg import caller
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
pytest_plugins=('tests.conftest',)

def create_application(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,source_provider=None,expires_after=None,suite_case_copies=1,judge_model_ref=None,judge_rule_ref=None):
    from aos_api.db import connect
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore,evaluation_candidate_ref
    from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
    from aos_api.aip_model_eval_request_store import AipModelEvalRequestStore,ModelEvalRequestBlocked
    from aos_api.aip_model_eval_action import propose_model_eval_request,decide_model_eval_request,ModelEvalActionBlocked
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.tenant_scope import TenantScope
    from aos_api.auth import resolve_principal
    from tests.aip.test_model_eval_request_pg import _register_original_model_eval_contract
    if judge_rule_ref is not None:
        # Test-only input must identify the exact governed Judge Model. The
        # caller test separately proves original signed publication; this
        # helper never grants rule, Model quality or execution authority.
        from aos_api.aip_eval_contracts import JudgeRevisionRef,AssetRevisionRef,AssetType
        exact_rule=JudgeRevisionRef.model_validate(judge_rule_ref)
        exact_model=VersionedAssetRef.model_validate(judge_model_ref)
        assert exact_model.asset_type=='RegisteredModelRevision'
        expected_route=AssetRevisionRef(asset_type=AssetType.REGISTERED_MODEL,asset_id=exact_model.asset_id,
            revision=str(exact_model.revision),content_hash=exact_model.content_hash)
        assert exact_rule.model_route==expected_route
    create_prefix(caller,issuer_factory,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path,source_provider=source_provider)
    base=Path(__file__).parent;prior=json.loads((base/'legal-model-prefix-application-r4.json').read_text())
    scope=TenantScope('org-org','dev-project');model=AipModelRuntimeStore().get_model(scope,prior['model_id'])
    target=evaluation_candidate_ref(model.model_copy(update={'revision':model.revision+1,'lifecycle':type(model.lifecycle).ACTIVE,'eval_gate_ref':None}))
    suffix=uuid4().hex;suite,contract=_register_original_model_eval_contract(scope,target,suffix)
    if suite_case_copies!=1 or judge_model_ref is not None:
        assert type(suite_case_copies) is int and suite_case_copies in (1,2)
        from aos_api.aip_eval_pack_registry import AipEvalPackRegistry,compute_eval_suite_hash
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import CreateEvalContractRequest
        prior_contract=AipProductionContractStore().get_eval_contract(scope,contract.contract_id,contract.revision)
        assert len(suite.cases)==1
        suite=suite.model_copy(update={'suite_id':suite.suite_id+'-two',
            'cases':[suite.cases[0].model_copy(update={'case_id':suite.cases[0].case_id+f'-{i}'}) for i in range(2)]})
        if judge_model_ref is not None:
            from aos_api.aip_eval_contracts import AssetRevisionRef,AssetType,JudgeRevisionRef
            from aos_api.aip_model_runtime_store import canonical_hash
            exact=VersionedAssetRef.model_validate(judge_model_ref)
            assert exact.asset_type=='RegisteredModelRevision'
            route=AssetRevisionRef(asset_type=AssetType.REGISTERED_MODEL,asset_id=exact.asset_id,revision=str(exact.revision),content_hash=exact.content_hash)
            spec={'schemaVersion':'aos.isolated-model-judge-reference/v1','modelRoute':route.model_dump(mode='json',by_alias=True),'executionAllowed':False}
            judge=JudgeRevisionRef(judge_id='isolated-model-judge-'+suffix,revision=1,content_hash=canonical_hash(spec),model_route=route)
            if judge_rule_ref is not None:
                judge=exact_rule
            suite=suite.model_copy(update={'judge':judge})
        suite=suite.model_copy(update={'content_hash':compute_eval_suite_hash(suite)})
        AipEvalPackRegistry().register_suite_revision(scope,suite,actor='test-maker')
        store_contract=AipProductionContractStore()
        body=CreateEvalContractRequest(suiteRef={'resourceType':'EvalSuiteRevision','resourceId':suite.suite_id,'revision':suite.revision,'contentHash':suite.content_hash},
            publicationRef=prior_contract.publication_ref,releaseGateRef=prior_contract.release_gate_ref,
            artifactSchemaRef=prior_contract.artifact_schema_ref,severityThresholds=prior_contract.severity_thresholds,
            gatePolicy=prior_contract.gate_policy,returnMapping=prior_contract.return_mapping,overridePolicy=prior_contract.override_policy)
        draft=store_contract.create_eval_contract(scope,'test-maker','two-case-contract-'+suffix,body)
        contract=store_contract.freeze_eval_contract(scope,'test-maker',draft.contract_id,draft.version,'two-case-freeze-'+suffix)
    expiry=datetime.now(UTC)+(expires_after if expires_after is not None else timedelta(minutes=10))
    source=VersionedAssetRef(assetType='RegisteredModelRevision',assetId=model.registered_model_id,revision=model.revision,contentHash=model.content_hash)
    request=ModelEvalRequestCreate(tenant=model.tenant,sourceRef=source,targetRef=target,expectedHeadVersion=prior['model_head']['version'],
        evalContractRef=VersionedAssetRef(assetType='EvalContractRevision',assetId=contract.contract_id,revision=contract.revision,contentHash=contract.content_hash),
        suiteRef=VersionedAssetRef(assetType='EvalSuiteRevision',assetId=suite.suite_id,revision=suite.revision,contentHash=suite.content_hash),
        providerRef=model.provider,priceRef=model.price_snapshot_ref,quotaPolicyRef=model.quota_policy_ref,budgetPolicyRef=model.budget_policy_ref,
        upperBoundMinor=10,expiresAt=expiry)
    store=AipModelEvalRequestStore()
    with pytest.raises(ModelEvalRequestBlocked):store.create(scope,model.created_by,'wrong-head-'+suffix,request.model_copy(update={'expected_head_version':7}))
    first=store.create(scope,model.created_by,'legal-eval-'+suffix,request)
    assert store.create(scope,model.created_by,'legal-eval-'+suffix,request)['request_id']==first['request_id']
    with connect(scope) as c:
        checker_subject=c.execute("SELECT checker_subject FROM aip_budget_cost_proposal WHERE proposal_id=%s",(prior['budget_refs']['proposalId'],)).fetchone()['checker_subject']
    sign=https_signer[0]
    maker=resolve_principal(token=sign(model.created_by),header_org=scope.org_id,header_project=scope.project_id)
    checker=resolve_principal(token=sign(checker_subject),header_org=scope.org_id,header_project=scope.project_id)
    proposal=propose_model_eval_request(maker,first['request_id'],'legal-eval-proposal-'+suffix,expiry)
    decision=DecideActionProposalRequest(expectedProposalVersion=proposal.proposal.version,expectedProposalHash=proposal.proposal.proposal_hash,decision='approved',reason='isolated application, no execution',approvalExpiresAt=expiry)
    with pytest.raises(ModelEvalActionBlocked,match='INDEPENDENT_CHECKER'):decide_model_eval_request(maker,proposal.proposal.id,'self-'+suffix,decision)
    approved=decide_model_eval_request(checker,proposal.proposal.id,'checker-'+suffix,decision)
    assert approved.proposal.status.value=='approved' and approved.proposal.policy_snapshot['executionAllowed'] is False
    assert len(approved.approvals)==1
    with connect(scope) as c:
        counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in ['aip_agent_run','aip_model_capacity_reservation']}
        counts['aip_model_eval_budget_reservation']=c.execute('SELECT count(*) AS n FROM aip_model_eval_budget_reservation WHERE org_id=%s AND project_id=%s AND request_id=%s',(*scope.key,first['request_id'])).fetchone()['n']
        assert all(n==0 for n in counts.values())
        assert c.execute("SELECT count(*) AS n FROM aip_release_gate_decision WHERE target_ref->>'assetId'=%s",(model.registered_model_id,)).fetchone()['n']==0
    result={'status':'ORIGINAL_NONEXECUTABLE_EVAL_APPLICATION_APPROVED','database':prior['database'],'model_id':model.registered_model_id,'model_hash':model.content_hash,'request_id':first['request_id'],'request_hash':first['request_hash'],'proposal_id':proposal.proposal.id,'maker':maker.subject,'checker':checker.subject,'expected_head_version':request.expected_head_version,'suite_id':suite.suite_id,'contract_id':contract.contract_id,'execution_allowed':False,'business_counts':counts,'count_scope':'Eval hold count is this exact request; AgentRun/capacity remain database-wide','limitations':['Test-owned dataset/redaction artifacts and actual deterministic Graph governance gate','Model-target Suite remains unexecuted; no Model quality gate','No budget hold, shared physical joint, unique execution Intent or formal business']}
    (base/'legal-eval-application-result-r4.json').write_text(json.dumps(result,indent=2)+'\n')
