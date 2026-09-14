"""Current original analysis to canonical pending data; grants no data access."""
from copy import deepcopy
from datetime import datetime, timedelta

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.ecommerce_business_investigation_data_command import RequestBusinessInvestigationMissingDataCommand
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_host_composition import build_ecommerce_growth_host_ports,build_runtime_ecommerce_growth_registry
from aos_api.ecommerce_growth_runtime_adapters import (
    TransactionBoundConnectFactory,_HostAnalysisReceiptStore,DataRequirementRequestHostService,
)


class AnalysisDataRequirementPreparation:
    def __init__(self, analysis):
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('exact original analysis service required')
        self._analysis=analysis

    @staticmethod
    def _request(request):
        if type(request) is not RequestBusinessInvestigationMissingDataCommand:
            raise TypeError('exact missing data intent required')
        return RequestBusinessInvestigationMissingDataCommand.model_validate_json(request.model_dump_json(),strict=True)

    def run_current(self, conn, *, claimed, request):
        request=self._request(request)
        with conn.transaction():
            return self._analysis._phase(conn,claimed,lambda snapshot,original,dispatch:
                self._during_current(conn,snapshot,original,dispatch,request))

    def run_completed(self, conn, *, receipt_ref, request):
        from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
        request=self._request(request)
        def current(context):
            root=context['analysisReceipt']
            original={key:root[key] for key in ('occurrenceRef','caseRef','profileRef','cutoffAt')}
            original['idempotencyKey']=context['originalIdempotencyKey']
            return self._during_current(conn,dict(source=context['source']),original,
                                        IssuedDispatchRef(**context['dispatch']),request)
        return AnalysisContinuationContext(self._analysis).run_current(conn,receipt_ref=receipt_ref,execute=current)

    def run_automatic_current(self, conn, *, claimed):
        with conn.transaction():
            return self._analysis._phase(conn,claimed,lambda snapshot,original,dispatch:
                self._during_automatic(conn,snapshot,original,dispatch))

    def run_automatic_completed(self, conn, *, receipt_ref):
        from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
        def current(context):
            root=context['analysisReceipt']
            original={key:root[key] for key in ('occurrenceRef','caseRef','profileRef','cutoffAt')}
            original['idempotencyKey']=context['originalIdempotencyKey']
            return self._during_automatic(conn,context,original,IssuedDispatchRef(**context['dispatch']))
        return AnalysisContinuationContext(self._analysis).run_current(conn,receipt_ref=receipt_ref,execute=current)

    def _during_automatic(self, conn, snapshot, original, dispatch):
        from aos_api.extension_runtime.configuration_store import read_configuration
        from aos_api.aip_runtime_configuration_authority import read_current_budget_ref
        installed=snapshot['growth']
        configuration=read_configuration(conn,org_id=self._analysis.scope.org_id,
            project_id=self._analysis.scope.project_id,
            installation_id=installed['installationRef']['installationId'],
            generation=installed['generation'],actor=self._analysis.source.actor,
            ref=installed['binding']['configRef'],
            authorize=self._analysis.source.reader._owner._authorization)
        budget=read_current_budget_ref(conn,org_id=self._analysis.scope.org_id,
            project_id=self._analysis.scope.project_id,ref=configuration.budgetRef)
        domain=EcommerceInvestigationProfileCatalog().read(snapshot['source']['case']['analysisType'])
        if domain is None:raise ValueError('current automatic data profile unavailable')
        cutoff=datetime.fromisoformat(original['cutoffAt'])
        policy=snapshot['source']['policy']
        # Fixed initial-store data policy v1. This ceiling neither reserves funds
        # nor authorizes reads; the original data/capability owners do that later.
        request=RequestBusinessInvestigationMissingDataCommand(
            purposeCode='initial_store_analysis',requiredFacts=list(domain[0].required_fact_profiles),
            timeWindow=dict(startAt=cutoff-timedelta(days=30),endAt=cutoff),grain='store',
            cutoffAt=cutoff,freshnessMaxAgeSeconds=policy['maxSourceAgeSeconds'],
            qualityThreshold=1.0,markings=sorted(installed['targetMarkings']),minPopulation=1,
            acceptableDegradation=[],requestedOutputs=['EvidenceBundleRevision'],
            budgetMinor=budget.daily_limit_minor,
            expiresAt=min(datetime.fromisoformat(policy['effectiveUntil']),budget.effective_until))
        return self._during_current(conn,snapshot,original,dispatch,request)

    def _during_current(self, conn, snapshot, original, analysis_dispatch, request):
        scope=self._analysis.scope
        tx=HostTransaction(conn)
        domain=EcommerceInvestigationProfileCatalog().read(snapshot['source']['case']['analysisType'])
        if domain is None or domain[0].exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=original['profileRef']:
            raise ValueError('current data profile differs from original event')
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (tuple(request.required_facts)!=domain[0].required_fact_profiles
                or request.cutoff_at!=datetime.fromisoformat(original['cutoffAt'])
                or not now<request.expires_at<=datetime.fromisoformat(snapshot['source']['policy']['effectiveUntil'])):
            raise ValueError('data intent differs from current original event')
        prior=_HostAnalysisReceiptStore(tx,scope).read(original['idempotencyKey'])
        if (prior is None or prior['phase']!='PREPARING' or prior['caseRef']!=original['caseRef']
                or prior['occurrenceRef']!=original['occurrenceRef'] or prior['profileRef']!=original['profileRef']
                or prior['cutoffAt']!=original['cutoffAt']):
            raise ValueError('original preparing analysis Receipt required')
        cases,runs,receipts,binder,data,_service=DataRequirementRequestHostService._components(tx,scope)
        run=runs.get_verified(scope,prior['runRef']['resourceId'])
        compilation=receipts.get_for_run(scope,InvestigationExactRef.model_validate(prior['runRef']))
        runtime=binder.bind_receipt(scope,compilation,run)
        checkpoint=runtime.checkpoint_ref
        if (checkpoint is None or compilation.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=prior['compilationRef']
                or runtime.task_run_ref.resource_id!=prior['taskRunRef']['resourceId']
                or runtime.task_run_ref.version!=prior['taskRunRef']['revision']
                or 'sha256:'+runtime.binding_hash!=prior['taskRunRef']['contentHash']):
            raise ValueError('original paused analysis lineage drifted')
        case=cases.get(scope,run.authority.case_ref.resource_id)
        key='analysis-initial-data-'+canonical_sha256([*scope.key,original['idempotencyKey']]).removeprefix('sha256:')
        command=dict(operation='data.requirement.request',idempotencyKey=key,expectedRunVersion=1,
            caseRef=original['caseRef'],runRef=prior['runRef'],
            checkpointRef=dict(resourceType='CheckpointRevision',resourceId=checkpoint.resource_id,
                revision=checkpoint.sequence,contentHash='sha256:'+checkpoint.state_hash),
            channelRef=case.channel_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
            entityRef=case.business_entity_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
            **request.model_dump(mode='json',by_alias=True))
        row=conn.execute("SELECT * FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_data_fulfill'",scope.key).fetchone()
        if row is None:raise ValueError('current data dispatch required')
        dispatch=IssuedDispatchRef(org_id=scope.org_id,project_id=scope.project_id,operation_id=row['operation_id'],
            handler_kind=row['handler_kind'],dispatch_revision=row['revision'],installation_id=str(row['installation_id']),
            generation=str(row['generation']),execution_epoch=row['execution_epoch'],cutover_group_id=str(row['cutover_group_id']),
            cutover_group_revision=row['cutover_group_revision'])
        for name in ('installation_id','generation','execution_epoch','cutover_group_id','cutover_group_revision'):
            if getattr(dispatch,name)!=getattr(analysis_dispatch,name):raise ValueError('data dispatch differs from analysis installation')
        ports=build_ecommerce_growth_host_ports(build_runtime_ecommerce_growth_registry(),
            connect_factory=TransactionBoundConnectFactory(tx,scope))
        result=ports.data_port.commit(dispatch_ref=dispatch,command=command)
        reference=result['requirementRef']
        saved=data.get_exact(scope,InvestigationExactRef.model_validate(reference))
        state=runs.get_verified(scope,run.authority.run_id).state
        if (state.lifecycle.value!='WAITING_DATA' or state.pending_requirement_ref!=InvestigationExactRef.model_validate(reference)
                or saved.required_facts!=request.required_facts or saved.status.value!='requested'):
            raise ValueError('pending data authority readback differs')
        return dict(requirementRef=deepcopy(reference),sourceReadPerformed=False,externalEffectAuthorized=False)
