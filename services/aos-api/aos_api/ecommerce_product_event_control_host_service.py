"""Current control Host service; registration requires the separate control contract."""
from datetime import datetime
from uuid import UUID
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ScheduleBinding
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
from aos_api.ecommerce_product_event_control_approval import require_current_event_control_approval,require_current_event_disable_actor
from aos_api.ecommerce_product_event_control_store import ProductEventBindingControlStore
from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
from aos_api.ecommerce_product_event_store import ProductEventPolicyStore
from aos_api.ecommerce_product_event_guard import ProductEventPolicyGuard
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.tenant_scope import TenantScope


class ProductEventControlHostService:
    executor_identity='ecommerce-growth-event-control-host'

    def __init__(self,owner,*,actor):
        if type(owner) is not ProductEventControlQualifiedOwner:
            raise TypeError('exact current control Owner required')
        if type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip() or not actor.isprintable():
            raise ValueError('authenticated control actor required')
        self._owner,self._actor=owner,actor
        self._guard=ProductEventPolicyGuard(owner)

    def _current(self,tx,scope,command):
        bound=ProductEventPolicyStore(tx,scope).get_current_binding(command.policy_ref.resource_id)
        if bound is None:
            raise ValueError('current event control policy unavailable')
        policy=bound['policy']
        expected=dict(resourceType='SchedulePolicyRevision',resourceId=policy['schedulePolicyId'],
            revision=policy['revision'],contentHash=policy['contentHash'],receiptId=None)
        if command.policy_ref.model_dump(by_alias=True,mode='json')!=expected:
            raise ValueError('current event control policy reference differs')
        return bound

    def _enable_check(self,tx,scope,dispatch,command,policy):
        AutomationOccurrenceStore._lock_policy(tx,scope,policy['schedulePolicyId'])
        tx.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',
            (policy['caseRef']['resourceId'],policy['schedulePolicyId'],command.approval_ref.resource_id))
        bound=self._current(tx,scope,command)
        if bound['policy']!=policy:
            raise ValueError('current event control policy changed')
        case=bound['caseAuthority']
        selection=EcommerceInvestigationProfileCatalog().read(case['analysisType'])
        if selection is None:
            raise ValueError('current control method unavailable')
        profile,method_scope=selection
        if (profile.exact_ref.model_dump(by_alias=True,mode='json')!=policy['methodRef']
                or method_scope.exact_ref.model_dump(by_alias=True,mode='json')!=case['scopeRef']):
            raise ValueError('current event control method differs')
        require_current_event_control_approval(transaction=tx,scope=scope,command=command,
            case_id=case['caseId'],executor=self._actor)
        target=tx.execute('''SELECT handler_kind,installation_id,generation,execution_epoch,
            operation_fence,cutover_group_id,cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance' ''',scope.key).fetchone()
        expected=('extension',UUID(str(dispatch.installation_id)),UUID(str(dispatch.generation)),
            dispatch.execution_epoch,False,UUID(str(dispatch.cutover_group_id)),dispatch.cutover_group_revision)
        if target is None or tuple(target[key] for key in ('handler_kind','installation_id','generation',
            'execution_epoch','operation_fence','cutover_group_id','cutover_group_revision'))!=expected:
            raise ValueError('current analysis target differs from locked control group')
        return ScheduleBinding(policy_id=policy['schedulePolicyId'],policy_revision=policy['revision'],
            policy_hash=policy['contentHash'],operation_id='ecommerce_growth_analysis_advance',
            installation_id=expected[1],generation=expected[2],execution_epoch=dispatch.execution_epoch,
            cadence='event',effective_from=datetime.fromisoformat(policy['effectiveFrom']),
            effective_until=datetime.fromisoformat(policy['effectiveUntil']),approved=True,enabled=True)

    def _run(self,*,transaction,scope,dispatch,command,write):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact control Host transaction and scope required')
        if dispatch.operation_id!='ecommerce_growth_event_control':
            raise ValueError('event control operation required')
        checked=ProductEventControlCommand.model_validate(command)
        if checked.intent=='disable':
            def stop():
                require_current_event_disable_actor(transaction=transaction,scope=scope,actor=self._actor)
                result=ProductEventBindingControlStore(transaction,scope).apply(checked,actor=self._actor) if write else None
                require_current_event_disable_actor(transaction=transaction,scope=scope,actor=self._actor)
                return result
            return transaction.run_current_event_control(self._owner,scope=scope,dispatch=dispatch,execute=stop)
        policy=self._current(transaction,scope,checked)['policy']
        def enable():
            binding=self._enable_check(transaction,scope,dispatch,checked,policy)
            result=ProductEventBindingControlStore(transaction,scope).apply(checked,actor=self._actor,binding=binding) if write else None
            if result is not None and result['replayed'] is False:
                from aos_api.ecommerce_installed_bootstrap_action import InstalledBootstrapActionCatalog
                InstalledBootstrapActionCatalog(transaction, scope).install(result)
            self._enable_check(transaction,scope,dispatch,checked,policy)
            return result
        return self._guard.run_policy(transaction=transaction,scope=scope,policy=policy,
            dispatch=dispatch,actor=self._actor,execute=enable)

    def revalidate(self,*,transaction,scope,dispatch,command):
        return self._run(transaction=transaction,scope=scope,dispatch=dispatch,command=command,write=False)

    def execute(self,*,transaction,scope,dispatch_ref,command,checked_at,occurred_at):
        return self._run(transaction=transaction,scope=scope,dispatch=dispatch_ref,command=command,write=True)

    def verify_receipt(self,*,transaction,scope,dispatch,command,receipt):
        if type(receipt) is not dict or type(receipt.get('replayed')) is not bool:
            return {}
        original=ProductEventControlReceiptStore(transaction,scope).find(command,actor=self._actor)
        if original is None:
            return {}
        expected=dict(original,replayed=receipt['replayed'])
        return expected if expected==receipt else {}
