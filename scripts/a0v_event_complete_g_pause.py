"""Pause only the exact G event binding while preserving unknown attempts."""
import argparse
import json
import a0v_event_complete_successor_business as g
import a0v_event_complete_product_policy as policy
from a0v_qyh_current_product_event_first_chain import freeze,_approve

STATE=g.STATE/'analysis-pause'
PREFIX='a0v-qyh-g-analysis-pause-20260916'


def run(phase):
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing pause intent requires read-only inspection')
    plane=g.setup()
    if phase=='approve':
        command=dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey=PREFIX+'-disable',policyRef=policy.load('put')['receiptRef'],expectedBindingRevision=1,intent='disable')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,controlIntent=command)
        freeze(intent,payload);bundle,ref=_approve('ecommerce_growth_event_control',payload,PREFIX+'-approval')
        result=dict(command=command,approvalRef=ref,proposalId=bundle.proposal.id)
    elif phase=='disable':
        from aos_api.auth import Principal
        from aos_api.tenant_scope import TenantScope
        from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        p=STATE/'approve-result.json'
        if p.stat().st_mode & 0o777!=0o600:raise ValueError('private pause approval required')
        approved=json.loads(p.read_text());command={**approved['command'],'approvalRef':approved['approvalRef']}
        freeze(intent,command);scope=TenantScope('org-org','dev-project')
        principal=Principal(subject=g.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
        router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal,plane.pipeline_control_factory))
        result=router.dispatch(scope=scope,operation_id='ecommerce_growth_event_control',command=command,expected_runtime=ExpectedRuntimeTarget(g.G_ID,g.G_GENERATION,3))
    else:raise ValueError('unsupported pause phase')
    freeze(STATE/(phase+'-result.json'),dict(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve','disable']);args=parser.parse_args()
    print(json.dumps(run(args.phase),default=str))
