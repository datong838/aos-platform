"""Bind the real QYH business Case to F's current Product event authority."""
import argparse
from datetime import datetime
import json
import sys
import a0v_growth19_successor_business as f
import a0v_growth19_product_authority as authority
from a0v_growth19_product_controlled_api import BUNDLE_ROOT

STATE=f.STATE/'product-event'
CASE='case-qyh-full-store-baseline-20260915'
POLICY='product-event-qyh-full-store-generation-f-20260916'
PREFIX='a0v-qyh-product-event-f-20260916-v1'


def load(phase):
    path=STATE/(phase+'-result.json')
    if path.stat().st_mode & 0o777!=0o600:raise ValueError('private event result required')
    return json.loads(path.read_text())


def prepare():
    from a0v_qyh_current_product_event_first_chain import _web_connection
    from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_budget_reservation_store import canonical_hash as approval_hash
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(f.ROOT/'packages/aos-extension-sdk/python'))
    sys.path.insert(0,str(BUNDLE_ROOT/'solution.ecommerce.growth/1.9.0/backend'))
    from ecommerce_growth.ecommerce_business_investigation_case import BusinessInvestigationCase,canonical_hash
    from ecommerce_growth.ecommerce_product_event_binding import prepare_event_case_binding
    from ecommerce_growth.ecommerce_product_event_schedule import ProductEventSchedulePolicy
    case=BusinessInvestigationCaseStore(_web_connection).get(TenantScope('org-org','dev-project'),CASE)
    original=case.model_dump(mode='json',by_alias=True)
    draft=authority.load('prepare')['draft'];authority.require_f(draft)
    start=datetime.fromisoformat(draft['notBefore']);end=datetime.fromisoformat(draft['expiresAt'])
    raw=dict(schemaVersion='aos.ecommerce.product-event-schedule-policy/v1',tenant=dict(orgId='org-org',projectId='dev-project'),
        schedulePolicyId=POLICY,revision=1,priorRef=None,
        caseRef=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case.case_id,revision=case.revision,contentHash=case.content_hash,receiptId=None),
        sourceSelectionRef=authority.load('selection')['ref'],methodRef=original['investigationProfileRef'],
        platform='niushop',shopId='1',objectTypes=['Product'],effectiveFrom=start.isoformat(),effectiveUntil=end.isoformat(),
        maxSourceAgeSeconds=3600,recoveryWindowSeconds=900,createdBy=f.ACTOR,createdAt=start.isoformat())
    raw['contentHash']=canonical_hash(raw)
    pair=prepare_event_case_binding(BusinessInvestigationCase.from_authority(original),ProductEventSchedulePolicy.from_authority(raw))
    policy=pair.policy.authority_payload()
    payload=dict(caseId=CASE,schedulePolicyId=POLICY,expectedPolicyRevision=0,expectedCaseVersion=case.version,policyHash=approval_hash(policy,prefixed=True))
    command=dict(idempotencyKey=PREFIX+'-policy-put',expectedPolicyRevision=0,expectedCaseVersion=case.version,
        policy={k:v for k,v in policy.items() if k!='tenant'},caseAuthority={k:v for k,v in pair.case.authority_payload().items() if k!='tenant'})
    return dict(originalCase=original,payload=payload,command=command)


def require_empty_failed_put(proof, expected_version):
    if (proof['policyCount']!=0 or proof['receiptCount']!=0
        or proof['case']['current_revision']!=expected_version
        or proof['case']['version']!=expected_version or proof['case']['lifecycle']!='ACTIVE'):
        raise ValueError('failed put is not proven absent')


def recheck_failed_put(command):
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as conn:
        policy=conn.execute("SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_head WHERE org_id='org-org' AND project_id='dev-project' AND schedule_policy_id=%s",(POLICY,)).fetchone()['n']
        receipt=conn.execute("SELECT count(*) AS n FROM ecommerce_investigation_schedule_policy_command_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s",(command['idempotencyKey'],)).fetchone()['n']
        case=conn.execute("SELECT current_revision,version,lifecycle FROM ecommerce_investigation_case_head WHERE org_id='org-org' AND project_id='dev-project' AND case_id=%s",(CASE,)).fetchone()
    if case is None:raise ValueError('original Case missing')
    proof=dict(policyCount=policy,receiptCount=receipt,case=dict(case))
    require_empty_failed_put(proof,command['expectedCaseVersion'])
    if json.loads((STATE/'put-intent.json').read_text())!=command:
        raise ValueError('original put intent differs')
    return proof


def run(phase,plane):
    from a0v_qyh_current_product_event_first_chain import freeze,_approve
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing event intent requires read-only inspection')
    if phase=='prepare':
        result=prepare();freeze(intent,dict(caseId=CASE,schedulePolicyId=POLICY))
    elif phase=='approve':
        payload=load('prepare')['payload'];freeze(intent,payload)
        bundle,ref=_approve('ecommerce_growth_schedule_put',payload,PREFIX+'-schedule-approval')
        result=dict(proposalId=bundle.proposal.id,approvalRef=ref)
    elif phase in ('put','put-recovered'):
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        from aos_api.tenant_scope import TenantScope
        command={**load('prepare')['command'],'approvalRef':load('approve')['approvalRef']}
        if phase=='put-recovered':
            proof=recheck_failed_put(command)
            freeze(STATE/'put-recovered-precheck.json',proof)
        freeze(intent,command);scope=TenantScope('org-org','dev-project')
        principal=Principal(subject=f.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
        router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal,plane.pipeline_control_factory))
        result=router.dispatch(scope=scope,operation_id='ecommerce_growth_schedule_put',command=command,
            expected_runtime=ExpectedRuntimeTarget(f.F_ID,f.F_GENERATION,3))
    else:raise ValueError('unknown event policy phase')
    result=dict(result,outcome='CURRENT_F_EVENT_POLICY_'+phase.upper())
    freeze(STATE/(phase+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','approve','put','put-recovered']);args=parser.parse_args()
    print(json.dumps(run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
