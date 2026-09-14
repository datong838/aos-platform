"""Read original pending data inside current analysis authority; no fulfillment."""
from copy import deepcopy
from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import DataRequirementRequestHostService
from aos_api.extension_runtime.runtime_gate import _reject_deferred


def _json(value):
    return value.model_dump(mode='json', by_alias=True, exclude_none=True)


class AnalysisPendingDataContext:
    def __init__(self, analysis):
        self._continuation = AnalysisContinuationContext(analysis)
        self.analysis = analysis

    def run_current(self, conn, *, receipt_ref, execute):
        if not callable(execute):
            raise TypeError('synchronous pending data consumer required')
        def consume(context):
            before = self._read(conn, context)
            digest = canonical_sha256(before)
            supplied = deepcopy(before)
            result = execute(supplied)
            _reject_deferred(result)
            if (canonical_sha256(supplied) != digest
                or canonical_sha256(self._read(conn, context)) != digest):
                raise ValueError('original pending data changed during consumption')
            return result
        return self._continuation.run_current(conn, receipt_ref=receipt_ref, execute=consume)

    def _read(self, conn, context):
        scope = self.analysis.scope
        root = context['analysisReceipt']
        cases, runs, receipts, binder, data, _ = DataRequirementRequestHostService._components(HostTransaction(conn), scope)
        run_ref = InvestigationExactRef.model_validate(root['runRef'])
        run = runs.get_verified(scope, run_ref.resource_id)
        if (run.authority.version != run_ref.revision or run.authority.content_hash != run_ref.content_hash
            or _json(run.authority.case_ref) != root['caseRef']
            or run.state.lifecycle.value != 'WAITING_DATA' or run.state.control.value != 'RUNNING'
            or run.state.uncertain_command is not None or run.state.pending_requirement_ref is None):
            raise ValueError('original running pending data state required')
        pending = run.state.pending_requirement_ref
        requirement = data.get_exact(scope, pending)
        current = data.get_current(scope, pending.resource_id)
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (current != requirement or requirement.status.value not in {'requested', 'accepted', 'planned'}
            or requirement.blockers or requirement.expires_at <= now):
            raise ValueError('current unexpired pending requirement required')
        compilation = receipts.get_for_run(scope, run_ref)
        runtime = binder.bind_receipt(scope, compilation, run)
        checkpoint = runtime.checkpoint_ref
        if (checkpoint is None or runtime.task_run_status.value != 'paused'
            or _json(compilation.exact_ref) != root['compilationRef']
            or runtime.task_run_ref.resource_id != root['taskRunRef']['resourceId']
            or runtime.task_run_ref.version != root['taskRunRef']['revision']
            or 'sha256:' + runtime.binding_hash != root['taskRunRef']['contentHash']):
            raise ValueError('original paused analysis runtime differs')
        checkpoint_ref = dict(resourceType='CheckpointRevision', resourceId=checkpoint.resource_id,
            revision=checkpoint.sequence, contentHash='sha256:' + checkpoint.state_hash)
        case = cases.get(scope, run.authority.case_ref.resource_id)
        profile = EcommerceInvestigationProfileCatalog().read(context['source']['case']['analysisType'])
        if (profile is None or _json(profile[0].exact_ref) != root['profileRef']
            or requirement.run_ref != run_ref or _json(requirement.case_ref) != root['caseRef']
            or _json(requirement.checkpoint_ref) != checkpoint_ref
            or requirement.channel_ref != case.channel_ref or requirement.entity_ref != case.business_entity_ref
            or requirement.purpose_code != context['source']['case']['analysisType']
            or tuple(requirement.required_facts) != profile[0].required_fact_profiles
            or requirement.cutoff_at != datetime.fromisoformat(root['cutoffAt'])):
            raise ValueError('pending data differs from original analysis lineage')
        return dict(schemaVersion='aos.analysis-pending-data-context/v1', analysisContext=deepcopy(context),
            requirementRef=_json(pending), requirement=_json(requirement), runState=_json(run.state),
            runtime=_json(runtime))
