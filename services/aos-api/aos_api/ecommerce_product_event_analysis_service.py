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
        return await self._handle(claimed,prepare_data=False)

    async def handle_with_data(self, claimed):
        """Worker entry: commit initialization and pending data as one outcome."""
        return await self._handle(claimed,prepare_data=True)

    async def _handle(self, claimed, *, prepare_data):
        with self.connect(self.scope) as conn:
            prepared,request=self._phase(conn,claimed,lambda snapshot,request,dispatch:(deepcopy(snapshot),deepcopy(request)))
        fingerprint=canonical_sha256(prepared)
        request_hash=canonical_sha256(request)
        from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
        resolved = EcommerceInvestigationProfileCatalog().read(prepared['source']['case']['analysisType'])
        if resolved is None:
            raise ValueError('current event analysis profile is unsupported')
        domain = resolved[0]
        if domain.exact_ref.model_dump(mode='json', by_alias=True, exclude_none=True) != request['profileRef']:
            raise ValueError('current event profile differs from catalog')
        command=await self.port.build_start(request)
        blueprint=await self.port.build_compilation_blueprint(domain)
        def commit(snapshot,current_request,dispatch):
            if canonical_sha256(snapshot)!=fingerprint or canonical_sha256(current_request)!=request_hash:
                raise ValueError('analysis current preparation changed')
            from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore
            existing = _HostAnalysisReceiptStore(HostTransaction(conn), self.scope).read(command['idempotencyKey'])
            if existing is None:
                self._initialize(conn, claimed=claimed, command=command, domain=domain, blueprint=blueprint)
            receipt = self._write(conn,claimed,dispatch,command)
            if prepare_data:
                from aos_api.ecommerce_analysis_data_preparation import AnalysisDataRequirementPreparation
                AnalysisDataRequirementPreparation(self)._during_automatic(conn,snapshot,current_request,dispatch)
            return receipt
        with self.connect(self.scope) as conn:
            receipt=self._phase(conn,claimed,commit)
            conn.commit()
        return receipt

    def _initialize(self, conn, *, claimed, command, domain, blueprint):
        from aos_api.aip_production_contracts import ProductionStartRequest, ActionProposalExactRef
        from aos_api.business_investigation_shared_contracts import InvestigationExactRef
        from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService
        from aos_api.ecommerce_analysis_context_preparation import AnalysisContextPreparation
        from aos_api.ecommerce_analysis_compilation_preparation import AnalysisCompilationPreparation
        from aos_api.ecommerce_analysis_startup_preview import AnalysisStartupPreviewPreparation
        from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
        from aos_api.ecommerce_analysis_bootstrap_action import AnalysisBootstrapActionPreparation, _BootstrapActionGuard
        from aos_api.ecommerce_analysis_bootstrap_start import _BootstrapProductionStartService
        tx = HostTransaction(conn)
        run = AnalysisAdvanceHostService()._prepare_start_run(transaction=tx, scope=self.scope, command=command,
            occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
        run_ref = InvestigationExactRef(resourceType='BusinessInvestigationRun', resourceId=run.authority.run_id,
            revision=run.authority.version, contentHash=run.authority.content_hash)
        prepared = AnalysisStartupPreviewPreparation(AnalysisCompilationPreparation(AnalysisContextPreparation(self))).run_current(
            conn, claimed=claimed, run_ref=run_ref, domain_profile=domain, blueprint=blueprint, execute=lambda value:value)
        current = AnalysisBootstrapCurrentBinding(self)
        action = AnalysisBootstrapActionPreparation(current).run_current(conn, claimed=claimed,
            intent=prepared['bootstrapIntent'], preview_ref=prepared['startupPreviewRef'], execute=lambda value:value)
        guard = _BootstrapActionGuard(current, conn, claimed, prepared['bootstrapIntent'], prepared['startupPreviewRef'])
        receipt = guard.intent.compilation_receipt
        task = conn.execute('SELECT version FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                            (*self.scope.key, receipt.task_id)).fetchone()
        body = ProductionStartRequest(taskId=receipt.task_id, expectedTaskVersion=task['version'],
            productionContextRef=guard.intent.compilation_binding.request.profile.production_context_ref,
            planRef=receipt.plan_ref, previewRef=guard.preview_ref,
            actionProposalRef=ActionProposalExactRef(proposalId=action.proposal.id, version=action.proposal.version,
                proposalHash=action.proposal.proposal_hash), logicGraphId=receipt.logic_ref.resource_id,
            logicRevision=receipt.logic_ref.revision, logicGraphHash=receipt.logic_ref.content_hash)
        key = 'analysis-bootstrap-start-' + canonical_sha256([*self.scope.key, command['idempotencyKey']]).removeprefix('sha256:')
        return _BootstrapProductionStartService(guard).start(self.scope, self.source.actor, key, body)

    def _source_group(self, conn):
        from aos_api.pipeline_snapshot_group_locator import PipelineSnapshotGroupLocator
        journal = self.source.reader._journal
        return PipelineSnapshotGroupLocator(claims=journal._claims).discover(
            conn, scope=self.scope, run_id=journal._run_id)

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
            group = self._source_group(conn)
            source_group = None
            cutoff = row['created_at'].astimezone(UTC).replace(microsecond=0)
            if group is not None:
                journal = self.source.reader._journal
                if (group.actor != self.source.actor
                        or (journal._ref, origin['runId']) not in group.bindings):
                    raise ValueError('analysis snapshot group differs from original source')
                cutoff = group.read_completed_at.astimezone(UTC)
                source_group = dict(groupId=group.group_id, manifestHash=group.manifest_hash,
                    readStartedAt=group.read_started_at.isoformat(), readCompletedAt=cutoff.isoformat())
            request=dict(kind='build_analysis_start',occurrenceRef=_occurrence_ref(occurrence),
                caseRef=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case['caseId'],
                             revision=case['revision'],contentHash=case['contentHash']),
                profileRef={key:value for key,value in case['investigationProfileRef'].items() if value is not None},
                cutoffAt=cutoff.isoformat(),
                idempotencyKey=claimed.target_idempotency_key)
            stable=dict(source=snapshot,growth=installed,occurrence=occurrence,origin=origin,request=request,
                        dispatchRevision=routing['revision'],groupRevision=routing['cutover_group_revision'])
            if source_group is not None:
                stable['sourceGroup'] = source_group
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
