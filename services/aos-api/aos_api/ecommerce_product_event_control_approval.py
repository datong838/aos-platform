"""Current identities and exact enable intent; no role grants or source bypass."""
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from aos_api.openfga import openfga_api_url
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_product_event_approval import _require_current_event_approval


def require_current_event_control_approval(*,transaction,scope,command,case_id,executor):
    checked=ProductEventControlCommand.model_validate(command)
    if checked.intent!='enable':
        raise ValueError('enable intent required for independent control approval')
    intent=checked.model_dump(by_alias=True,mode='json')
    intent.pop('approvalRef')
    return _require_current_event_approval(transaction=transaction,scope=scope,case_id=case_id,
        policy_id=checked.policy_ref.resource_id,approval_ref=checked.approval_ref,executor=executor,
        action_type='ecommerce_growth_event_control',expected_payload=dict(caseId=case_id,
            schedulePolicyId=checked.policy_ref.resource_id,controlIntent=intent))


def require_current_event_disable_actor(*,transaction,scope,actor):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('current Host transaction and scope required')
    if (type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip()
            or not actor.isprintable() or openfga_api_url()):
        raise PermissionError('current control identity adapter required')
    identity=transaction.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
        "current_setting('aos.project_id',true) AS project_id").fetchone()
    if identity is None or (identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key):
        raise PermissionError('current runtime control scope required')
    rows=transaction.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s '
        'AND subject=%s FOR SHARE',(*scope.key,actor)).fetchall()
    if len(rows)!=1 or rows[0]['role'].lower() not in {'admin','owner'}:
        raise PermissionError('current tenant control role required')
