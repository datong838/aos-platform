"""Current-source prepare, installed pure computation, current-source commit."""
from copy import deepcopy
from datetime import datetime
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_product_event_control_host_service import ProductEventControlHostService
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
from aos_api.ecommerce_product_event_guard import ProductEventPolicyGuard
from aos_api.ecommerce_product_event_reader import ProductEventCandidateReader
from aos_api.ecommerce_product_event_store import ProductEventPolicyStore
from aos_api.ecommerce_product_event_window_port import InstalledProductEventWindowPort
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
from aos_api.tenant_scope import TenantScope


class ProductEventConsumptionService:
    def __init__(self, *, scope, actor, owner, reader, invoker):
        if (type(scope) is not TenantScope or type(owner) is not ProductEventControlQualifiedOwner
                or type(reader) is not ProductEventCandidateReader
                or type(invoker) is not CurrentInstalledPackageInvoker):
            raise TypeError('exact current event consumption dependencies required')
        if (reader._owner is not owner._source or invoker.scope != scope
                or reader._journal._scope != scope or reader._journal._actor != actor):
            raise ValueError('event consumption dependency scope differs')
        self.scope,self.actor,self.reader,self.invoker=scope,actor,reader,invoker
        self.control=ProductEventControlHostService(owner,actor=actor)
        self.guard=ProductEventPolicyGuard(owner)
        self.port=InstalledProductEventWindowPort(invoker)
        self.connect=connect_serializable

    async def consume(self,policy_id):
        if type(policy_id) is not str or not 1<=len(policy_id)<=200 or policy_id!=policy_id.strip() or not policy_id.isprintable():
            raise ValueError('canonical event policy identity required')
        with self.connect(self.scope) as conn:
            prepared,request=self._phase(conn,policy_id,lambda snapshot,request,_binding:(deepcopy(snapshot),deepcopy(request)))
        if request is None:
            return ()
        fingerprint=canonical_sha256(prepared)
        request_hash=canonical_sha256(request)
        result=await self.port.calculate(request)
        def commit(snapshot,current_request,binding):
            if (canonical_sha256(snapshot)!=fingerprint or current_request is None
                    or canonical_sha256(current_request)!=request_hash):
                raise ValueError('event consumption current snapshot changed')
            return self._write(conn,binding,result)
        with self.connect(self.scope) as conn:
            writes=self._phase(conn,policy_id,commit)
            conn.commit()
        return writes

    def _write(self,conn,binding,result):
        store=AutomationOccurrenceStore(TransactionBoundConnectFactory(HostTransaction(conn),self.scope))
        return store.record_event_batch(self.scope,binding,events=[
            (row['eventKey'],datetime.fromisoformat(row['deadline'])) for row in result['events']])

    def _phase(self,conn,policy_id,consume,*,exact_event_key=None):
        scope=self.scope;tx=HostTransaction(conn)
        row=tx.execute('''SELECT * FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_event_control' ''',scope.key).fetchone()
        if row is None or row['handler_kind']!='extension' or row['operation_fence'] is not False:
            raise PermissionError('current event control dispatch required')
        issued=IssuedDispatchRef(org_id=scope.org_id,project_id=scope.project_id,
            operation_id='ecommerce_growth_event_control',handler_kind='extension',dispatch_revision=row['revision'],
            installation_id=str(row['installation_id']),generation=str(row['generation']),execution_epoch=row['execution_epoch'],
            cutover_group_id=str(row['cutover_group_id']),cutover_group_revision=row['cutover_group_revision'])
        dispatch=LockedEcommerceGrowthHostPort._lock_and_revalidate(conn,scope,issued)
        if (str(self.invoker.installation_id),str(self.invoker.generation))!=(issued.installation_id,issued.generation):
            raise PermissionError('core invocation differs from current event installation')
        current=ProductEventPolicyStore(tx,scope).get_current_binding(policy_id)
        if current is None:
            raise ValueError('current event policy unavailable')
        policy=current['policy']
        def source_current(context):
            AutomationOccurrenceStore._lock_policy(tx,scope,policy_id)
            controls=tx.execute('''SELECT r.command,b.revision FROM automation_schedule_binding b
                JOIN ecommerce_product_event_control_receipt r
                  ON r.org_id=b.org_id AND r.project_id=b.project_id AND r.policy_id=b.policy_id
                 AND r.policy_revision=b.policy_revision AND r.binding_revision=b.revision
                WHERE b.org_id=%s AND b.project_id=%s AND b.policy_id=%s AND b.policy_revision=%s
                  AND b.cadence='event' AND b.enabled AND b.approved''',
                (*scope.key,policy_id,policy['revision'])).fetchall()
            if len(controls)!=1:
                raise PermissionError('current enabled event receipt required')
            command=ProductEventControlCommand.model_validate(controls[0]['command'])
            if command.intent!='enable' or command.expected_binding_revision+1!=controls[0]['revision']:
                raise PermissionError('current event enable revision differs')
            receipt=ProductEventControlReceiptStore(tx,scope).find(command,actor=self.actor)
            if receipt is None:
                raise PermissionError('original event enable receipt required')
            binding=self.control._enable_check(tx,scope,dispatch,command,policy)
            AutomationOccurrenceStore._lock_binding(tx,scope,binding)
            def candidates(rows):
                installed=self.invoker.read_current_in_transaction(tx)
                metadata=[{key:value.isoformat() if isinstance(value,datetime) else value
                           for key,value in item.items()} for item in rows]
                snapshot=dict(policy=policy,case=self.control._current(tx,scope,command)['caseAuthority'],bindingRevision=controls[0]['revision'],
                    controlReceipt=receipt,installed=installed,events=metadata,
                    dispatch=dict(revision=issued.dispatch_revision,groupRevision=issued.cutover_group_revision,
                        groupId=issued.cutover_group_id,installationId=issued.installation_id,
                        generation=issued.generation,executionEpoch=issued.execution_epoch))
                request=None if not rows else dict(schemaVersion='aos.product-event-window-request/v1',
                    effectiveFrom=policy['effectiveFrom'],effectiveUntil=policy['effectiveUntil'],
                    maxSourceAgeSeconds=policy['maxSourceAgeSeconds'],recoveryWindowSeconds=policy['recoveryWindowSeconds'],
                    events=[dict(eventKey=item['event_key'],sourceUpdatedAt=item['source_updated_at'],
                        recordedAt=item['created_at'].isoformat()) for item in rows])
                result=consume(snapshot,request,binding)
                self.control._enable_check(tx,scope,dispatch,command,policy)
                AutomationOccurrenceStore._lock_binding(tx,scope,binding)
                if self.invoker.read_current_in_transaction(tx)!=installed:
                    raise PermissionError('current core installation changed')
                return result
            if exact_event_key is not None:
                return self.reader.run_event(conn,policy=context,actor=self.actor,
                    run_id=self.reader._journal._run_id,event_key=exact_event_key,
                    execute=lambda row:candidates((row,)))
            return self.reader.run_candidates(conn,policy=context,actor=self.actor,
                run_id=self.reader._journal._run_id,execute=candidates)
        return self.guard.run_policy_context(transaction=tx,scope=scope,policy=policy,
            dispatch=dispatch,actor=self.actor,execute=source_current)
