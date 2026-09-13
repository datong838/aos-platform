"""Original event and current claim to the sealed analysis Host transaction."""
from copy import deepcopy
from datetime import UTC

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ClaimedOccurrence
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_composition import build_runtime_ecommerce_growth_registry, build_ecommerce_growth_host_ports
from aos_api.ecommerce_growth_host_ports import HostTransaction, LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, _occurrence_payload, _occurrence_ref
from aos_api.ecommerce_product_event_analysis_port import InstalledProductEventAnalysisPort
from aos_api.ecommerce_product_event_consumer import ProductEventConsumptionService
from aos_api.ecommerce_product_event_origin import ProductEventOriginStore
from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker


class ProductEventAnalysisService:
    def __init__(self, *, source_context, invoker):
        if type(source_context) is not ProductEventConsumptionService or type(invoker) is not CurrentInstalledPackageInvoker:
            raise TypeError('exact current source context and installed invoker required')
        core=source_context.invoker
        if (invoker.scope,invoker.installation_id,invoker.generation)!=(core.scope,core.installation_id,core.generation):
            raise ValueError('analysis and source installation differ')
        self.source=source_context
        self.invoker=invoker
        self.scope=source_context.scope
        self.connect=source_context.connect
        self.port=InstalledProductEventAnalysisPort(invoker)

    async def handle(self, claimed):
        with self.connect(self.scope) as conn:
            prepared,request=self._phase(conn,claimed,lambda snapshot,request,dispatch:(deepcopy(snapshot),deepcopy(request)))
        fingerprint=canonical_sha256(prepared)
        request_hash=canonical_sha256(request)
        command=await self.port.build_start(request)
        def commit(snapshot,current_request,dispatch):
            if canonical_sha256(snapshot)!=fingerprint or canonical_sha256(current_request)!=request_hash:
                raise ValueError('analysis current preparation changed')
            return self._write(conn,claimed,dispatch,command)
        with self.connect(self.scope) as conn:
            receipt=self._phase(conn,claimed,commit)
            conn.commit()
        return receipt

    def _phase(self,conn,claimed,execute):
        if type(claimed) is not ClaimedOccurrence or claimed.operation_id!='ecommerce_growth_analysis_advance':
            raise ValueError('exact analysis claim required')
        scope=self.scope;tx=HostTransaction(conn)
        origin=ProductEventOriginStore(tx,scope).read(claimed.occurrence_id)
        if (origin is None or origin['runId']!=self.source.reader._journal._run_id
                or origin['actor']!=self.source.actor):
            raise ValueError('analysis source differs from original event batch')
        event_key=origin['sourceEventId']
        def current(snapshot,_window,binding):
            row=AutomationOccurrenceStore._lock_claim(conn,scope,claimed)
            if (row['trigger_source']!='event' or row['source_event_id']!=event_key
                    or row['policy_hash']!=binding.policy_hash or row['policy_revision']!=binding.policy_revision
                    or row['installation_id']!=binding.installation_id or row['generation']!=binding.generation
                    or row['execution_epoch']!=binding.execution_epoch):
                raise ValueError('claimed event differs from current policy')
            routing=tx.execute('SELECT * FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s AND operation_id=%s',
                               (*scope.key,claimed.operation_id)).fetchone()
            if routing is None:
                raise ValueError('current analysis dispatch missing')
            issued=IssuedDispatchRef(org_id=scope.org_id,project_id=scope.project_id,
                operation_id=claimed.operation_id,handler_kind=routing['handler_kind'],dispatch_revision=routing['revision'],
                installation_id=str(routing['installation_id']),generation=str(routing['generation']),execution_epoch=routing['execution_epoch'],
                cutover_group_id=str(routing['cutover_group_id']),cutover_group_revision=routing['cutover_group_revision'])
            LockedEcommerceGrowthHostPort._lock_and_revalidate(conn,scope,issued)
            installed=self.invoker.read_current_in_transaction(tx)
            occurrence=_occurrence_payload(tx,scope,claimed.occurrence_id)
            case=snapshot['case']
            request=dict(kind='build_analysis_start',occurrenceRef=_occurrence_ref(occurrence),
                caseRef=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case['caseId'],
                             revision=case['revision'],contentHash=case['contentHash']),
                profileRef={key:value for key,value in case['investigationProfileRef'].items() if value is not None},
                cutoffAt=row['created_at'].astimezone(UTC).replace(microsecond=0).isoformat(),
                idempotencyKey=claimed.target_idempotency_key)
            stable=dict(source=snapshot,growth=installed,occurrence=occurrence,origin=origin,request=request,
                        dispatchRevision=routing['revision'],groupRevision=routing['cutover_group_revision'])
            result=execute(stable,request,issued)
            AutomationOccurrenceStore._lock_claim(conn,scope,claimed)
            if self.invoker.read_current_in_transaction(tx)!=installed:
                raise ValueError('current growth installation changed')
            return result
        return self.source._phase(conn,claimed.policy_id,current,exact_event_key=event_key)

    def _write(self,conn,claimed,dispatch,command):
        ports=build_ecommerce_growth_host_ports(build_runtime_ecommerce_growth_registry(),
            connect_factory=TransactionBoundConnectFactory(HostTransaction(conn),self.scope))
        result=ports.runtime_port.commit(dispatch_ref=dispatch,command=command)
        AutomationOccurrenceStore._lock_claim(conn,self.scope,claimed)
        return deepcopy(result['receiptRef'])
