"""One recovery of a confirmed lock-timeout rollback; never retry unknown writes."""
import json
from contextlib import contextmanager
from a0v_i_product_pause import load_profile
from a0v_formal_text_model_renewal import database_connect
from a0v_qyh_current_product_event_first_chain import freeze


def run():
    p=load_profile();state=p.STATE/'lock-recovery';intent=state/'intent.json'
    if intent.exists():raise ValueError('existing recovery intent requires readback')
    plane=p.g.setup()
    original=json.loads((p.STATE/'disable-intent.json').read_text())
    approved=json.loads((p.STATE/'approve-result.json').read_text())
    if original!={**approved['command'],'approvalRef':approved['approvalRef']}:
        raise ValueError('original pause command differs')
    with database_connect('aos_meta_head')() as c:
        found=c.execute("SELECT 1 FROM ecommerce_product_event_control_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s",(original['idempotencyKey'],)).fetchone()
        row=c.execute("SELECT enabled,revision FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s AND policy_revision=6",(p.policy.POLICY,)).fetchone()
    if found or row!=dict(enabled=True,revision=1):raise ValueError('pause outcome requires inspection')
    from aos_api.auth import Principal
    from aos_api.tenant_scope import TenantScope
    from aos_api.ecommerce_growth_runtime_connection import connect_serializable
    from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
    from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
    @contextmanager
    def maintenance(scope):
        with connect_serializable(scope) as conn:
            conn.execute("SET LOCAL lock_timeout='25s'")
            yield conn
    scope=TenantScope('org-org','dev-project')
    principal=Principal(subject=p.g.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
    router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal,plane.pipeline_control_factory),connect_factory=maintenance)
    freeze(intent,original)
    result=router.dispatch(scope=scope,operation_id='ecommerce_growth_event_control',command=original,expected_runtime=ExpectedRuntimeTarget(p.g.G_ID,p.g.G_GENERATION,3))
    freeze(state/'result.json',result)
    return result


if __name__=='__main__':print(json.dumps(run(),default=str))
