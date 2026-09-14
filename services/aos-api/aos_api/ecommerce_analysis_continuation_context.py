"""Current source context for an accepted original analysis, never an expired Claim."""
from copy import deepcopy
from uuid import UUID

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.ecommerce_product_event_origin import ProductEventOriginStore
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_host_ports import HostTransaction,LockedEcommerceGrowthHostPort
from aos_api.ecommerce_growth_runtime_adapters import (
    _analysis_exact_ref,_occurrence_payload,_HostAnalysisReceiptStore,AnalysisAdvanceHostService,
)
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisContinuationContext:
    def __init__(self, analysis):
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('exact original analysis context required')
        self.analysis=analysis

    def run_current(self, conn, *, receipt_ref, execute):
        reference=_analysis_exact_ref(receipt_ref,'AnalysisRuntimeReceipt',receipt_required=True)
        if not callable(execute):raise TypeError('synchronous continuation callback required')
        scope=self.analysis.scope
        tx=HostTransaction(conn)
        refs=reference.model_dump(mode='json',by_alias=True,exclude_none=True)
        with conn.transaction():
            receipt=_HostAnalysisReceiptStore(tx,scope).read_exact(refs)
            if receipt is None:raise ValueError('original analysis Receipt missing')
            occurrence_id=UUID(receipt['occurrenceRef']['resourceId'])
            origin=ProductEventOriginStore(tx,scope).read(occurrence_id)
            if (origin is None or origin['runId']!=self.analysis.source.reader._journal._run_id
                    or origin['actor']!=self.analysis.source.actor):
                raise ValueError('continuation differs from original source batch')
            occurrence=_occurrence_payload(tx,scope,occurrence_id)
            def current(source,_window,binding):
                before=self._read(tx,scope,refs,occurrence_id,origin,source,binding)
                result=execute(deepcopy(before))
                _reject_deferred(result)
                after=self._read(tx,scope,refs,occurrence_id,origin,source,binding)
                if canonical_sha256(before)!=canonical_sha256(after):
                    raise ValueError('current continuation context changed')
                return result
            return self.analysis.source._phase(conn,occurrence['policyId'],current,
                exact_event_key=origin['sourceEventId'])

    def _read(self, tx, scope, receipt_ref, occurrence_id, origin, source, binding):
        occurrence=_occurrence_payload(tx,scope,occurrence_id)
        if occurrence['status']!='accepted':raise ValueError('completed original analysis event required')
        historical=AnalysisAdvanceHostService._accepted_occurrence_reference(tx,scope,occurrence)
        receipt=_HostAnalysisReceiptStore(tx,scope).read_exact(receipt_ref)
        target=tx.execute('SELECT receipt_ref FROM automation_occurrence WHERE org_id=%s AND project_id=%s AND occurrence_id=%s',
                          (*scope.key,occurrence_id)).fetchone()
        if target is None or target['receipt_ref']!=receipt_ref:
            raise ValueError('continuation must use the recorded original target Receipt')
        case=source['case']
        case_ref=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case['caseId'],
                      revision=case['revision'],contentHash=case['contentHash'])
        profile={k:v for k,v in case['investigationProfileRef'].items() if v is not None}
        if (receipt is None or receipt['phase']!='PREPARING' or receipt['occurrenceRef']!=historical
                or receipt['caseRef']!=case_ref or receipt['profileRef']!=profile
                or ProductEventOriginStore(tx,scope).read(occurrence_id)!=origin
                or occurrence['policyId']!=binding.policy_id or occurrence['policyRevision']!=binding.policy_revision
                or occurrence['policyHash']!=binding.policy_hash
                or occurrence['installationId']!=str(binding.installation_id)
                or occurrence['generation']!=str(binding.generation) or occurrence['executionEpoch']!=binding.execution_epoch):
            raise ValueError('completed analysis current source lineage drifted')
        row=tx.execute("SELECT * FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_analysis_advance'",scope.key).fetchone()
        if row is None:raise ValueError('current analysis dispatch required')
        dispatch=IssuedDispatchRef(org_id=scope.org_id,project_id=scope.project_id,operation_id=row['operation_id'],
            handler_kind=row['handler_kind'],dispatch_revision=row['revision'],installation_id=str(row['installation_id']),
            generation=str(row['generation']),execution_epoch=row['execution_epoch'],cutover_group_id=str(row['cutover_group_id']),
            cutover_group_revision=row['cutover_group_revision'])
        LockedEcommerceGrowthHostPort._lock_and_revalidate(tx,scope,dispatch)
        if (dispatch.installation_id!=occurrence['installationId'] or dispatch.generation!=occurrence['generation']
                or dispatch.execution_epoch!=occurrence['executionEpoch']
                or str(self.analysis.invoker.installation_id)!=dispatch.installation_id
                or str(self.analysis.invoker.generation)!=dispatch.generation):
            raise ValueError('continuation installation differs from original event')
        installed=self.analysis.invoker.read_current_in_transaction(tx)
        return dict(source=deepcopy(source),growth=deepcopy(installed),origin=deepcopy(origin),
            occurrence=occurrence,analysisReceipt=deepcopy(receipt),
            dispatch=dict(revision=dispatch.dispatch_revision,groupId=dispatch.cutover_group_id,
                          groupRevision=dispatch.cutover_group_revision))
