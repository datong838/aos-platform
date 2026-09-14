"""Original readiness receipts remain usable only under current snapshot owners."""
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.ecommerce_analysis_snapshot_readiness_context import AnalysisSnapshotReadinessContext
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.source_readiness import SourceReadinessService
from aos_api.source_readiness_contracts import (
    ExactResourceRef, InvestigationReadinessProjection, SourceReadinessEnvelope,
)
from aos_api.source_readiness_receipt_store import SourceReadinessReceiptStore


def _with_requirement(value, requirement, business):
    envelope=SourceReadinessService.evaluate_installed_snapshot(value)
    req=DataRequirementRevisionRecord.model_validate(requirement)
    expected=dict(resourceType='DataRequirementRevision',resourceId=req.requirement_id,
        revision=req.revision,contentHash=req.content_hash)
    if business['requirementRef']!=expected or req.tenant!=envelope.tenant:
        raise ValueError('readiness requires the original exact requirement')
    required=set(req.required_facts)
    covered=set(business['factIds'])
    if not covered<=required:
        raise ValueError('readiness contains unrequested facts')
    unmet=sorted(required-covered)
    projection=InvestigationReadinessProjection(
        requirement_ref=ExactResourceRef(resource_type='DataRequirementRevision',resource_id=req.requirement_id,
            revision=str(req.revision),content_hash=req.content_hash.removeprefix('sha256:'),authority='postgres:data_requirement_revision'),
        status=envelope.status,evaluated_at=envelope.checked_at,required_cutoff=req.cutoff_at,
        freshness_expires_at=min(s.freshness_expires_at for s in envelope.sources),
        required_fact_count=len(required),covered_fact_count=len(covered),coverage_ratio=len(covered)/len(required),
        unmet_facts=unmet,blockers=[dict(code='SNAPSHOT_SOURCE_NOT_READY',fact=s.object_type,
            source_ids=[s.pipeline_id],reason=';'.join(s.reasons+s.blockers) or s.status.value)
            for s in envelope.sources if s.status!='ready'])
    return SourceReadinessEnvelope.model_validate(envelope.model_copy(update={'investigation':projection}).model_dump())


def _match_current(saved,current):
    """Compare original facts while preserving the receipt's stricter time bound."""
    if saved.checked_at>current.checked_at or saved.investigation is None:
        raise ValueError('readiness receipt has no current requirement or is from the future')
    expected=current.model_copy(deep=True)
    for old,new in zip(saved.sources,expected.sources):
        if (old.freshness_expires_at is None or new.freshness_expires_at is None
                or not current.checked_at<old.freshness_expires_at<=new.freshness_expires_at):
            raise ValueError('readiness receipt expired or exceeds current authority')
        new.checked_at=saved.checked_at
        new.freshness_expires_at=old.freshness_expires_at
    expected.checked_at=saved.checked_at
    expected.investigation.evaluated_at=saved.checked_at
    expected.investigation.freshness_expires_at=min(s.freshness_expires_at for s in expected.sources)
    expected.receipt_ref=saved.receipt_ref
    expected=SourceReadinessEnvelope.model_validate(expected.model_dump())
    if expected!=saved:
        raise ValueError('readiness receipt differs from current original facts')


def _require_unexpired(saved,now):
    if any(s.freshness_expires_at is None or now>=s.freshness_expires_at for s in saved.sources):
        raise ValueError('readiness receipt expired during consumption')


class AnalysisSnapshotReadiness:
    def __init__(self,context):
        if type(context) is not AnalysisSnapshotReadinessContext:
            raise TypeError('original current readiness context required')
        self.context=context
        self.scope=context.scope

    def _during(self,conn,*,business_ref,policy_ref,execute):
        def consume(value):
            body=self.context.business._record(conn,business_ref)
            source=self.context.source._record(conn,body['selection']['evidenceRef'])
            current=_with_requirement(value,source['fieldContext']['requirement'],body)
            before=current.model_dump(mode='json')
            result=execute(SourceReadinessReceiptStore(HostTransaction(conn),self.scope),current)
            _reject_deferred(result)
            if current.model_dump(mode='json')!=before:
                raise ValueError('readiness decision changed during consumption')
            return result
        return self.context.run_current(conn,business_ref=business_ref,policy_ref=policy_ref,execute=consume)

    def put_current(self,conn,*,business_ref,policy_ref):
        def save(store,current):
            saved=store.put(current)
            if store.read_exact(saved.receipt_ref)!=saved:
                raise ValueError('readiness receipt persistence differs')
            return saved
        return self._during(conn,business_ref=business_ref,policy_ref=policy_ref,execute=save)

    def read_current(self,conn,*,reference,business_ref,policy_ref):
        return self.run_current(conn,reference=reference,business_ref=business_ref,
            policy_ref=policy_ref,execute=lambda saved:saved.model_copy(deep=True))

    def run_current(self,conn,*,reference,business_ref,policy_ref,execute):
        if not callable(execute):raise TypeError('synchronous receipt consumer required')
        ref=ExactResourceRef.model_validate(reference.model_dump() if isinstance(reference,ExactResourceRef) else reference)
        def consume(store,current):
            saved=store.read_exact(ref)
            if saved is None:raise LookupError('readiness receipt unavailable')
            _match_current(saved,current)
            before=saved.model_dump(mode='json')
            result=execute(saved)
            _reject_deferred(result)
            _require_unexpired(saved,HostTransaction(conn).execute('SELECT clock_timestamp() AS now').fetchone()['now'])
            if saved.model_dump(mode='json')!=before or store.read_exact(ref)!=saved:
                raise ValueError('readiness receipt changed during consumption')
            return result
        return self._during(conn,business_ref=business_ref,policy_ref=policy_ref,execute=consume)
