"""Fixed original snapshot delivery and resume sequence; no Outbox acknowledgement."""
from uuid import UUID

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRoute
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBrief
from aos_api.ecommerce_analysis_snapshot_bundle import AnalysisSnapshotBundle
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence
from aos_api.ecommerce_analysis_snapshot_fulfillment import AnalysisSnapshotFulfillment
from aos_api.ecommerce_analysis_snapshot_policy_set import AnalysisSnapshotPolicySetOwner
from aos_api.ecommerce_analysis_snapshot_quality_evidence import AnalysisSnapshotQualityEvidence
from aos_api.ecommerce_analysis_snapshot_readiness import AnalysisSnapshotReadiness
from aos_api.ecommerce_analysis_snapshot_readiness_context import AnalysisSnapshotReadinessContext
from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession
from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext
from aos_api.ecommerce_analysis_snapshot_source_evidence import AnalysisSnapshotSourceEvidence
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore, _analysis_command_hash
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion


def snapshot_route_key(scope, requirement_ref):
    """Original tenant-bound idempotency key shared with read-only diagnostics."""
    return 'snapshot-route-'+canonical_sha256(dict(tenant=dict(
        orgId=scope.org_id,projectId=scope.project_id),
        requirementRef=requirement_ref))[7:]


class AnalysisSnapshotCoordinator:
    """Trusted synchronous composition after routing and before delivery ack."""

    def __init__(self, *, analysis, completion, store):
        if (type(analysis) is not ProductEventAnalysisService
                or type(completion) is not PipelineSnapshotGroupCompletion
                or type(store) is not EcomConsistencyStore):
            raise TypeError('exact original snapshot coordinator dependencies required')
        claims=analysis.source.reader._journal._claims
        if completion._claims is not claims or completion._store is not store:
            raise ValueError('snapshot coordinator Owners must share one original source')
        self.analysis,self.completion,self.store=analysis,completion,store
        self.policies=AnalysisSnapshotPolicySetOwner(controls=claims._controls)

    def _validate_route(self, conn, route):
        if type(route) is not AnalysisDataRequirementRoute:
            raise TypeError('exact original DataRequirement route required')
        scope=self.analysis.scope
        identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        _require_transaction(conn)
        journal=self.analysis.source.reader._journal
        if ((identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key)
                or route.requirement.tenant.org_id!=scope.org_id
                or route.requirement.tenant.project_id!=scope.project_id
                or route.actor!=self.analysis.source.actor
                or route.source_run_id!=journal._run_id or route.source_control_ref!=journal._ref
                or route.installation_id!=str(self.analysis.invoker.installation_id)
                or route.generation!=str(self.analysis.invoker.generation)
                or str(UUID(route.occurrence_id))!=route.occurrence_id):
            raise ValueError('original analysis and DataRequirement route differs')
        matches=[pair for pair in route.group_bindings if pair==(route.source_control_ref,route.source_run_id)]
        if len(matches)!=1:
            raise ValueError('original analysis source is not unique in route')

    @staticmethod
    def _json(value):
        return value.model_dump(mode='json',by_alias=True,exclude_none=True)

    def _resume(self, conn, route, current, root, *, requirement_ref, fulfillment_ref,
                readiness_ref, bundle_ref, observed_at, business_ref, fulfillment):
        key=snapshot_route_key(self.analysis.scope,self._json(requirement_ref))
        command=dict(operation='runtime.analysis.resume_snapshot',
            idempotencyKey=key,
            occurrenceRef=root['occurrenceRef'],caseRef=root['caseRef'],profileRef=root['profileRef'],
            cutoffAt=root['cutoffAt'],priorReceiptRef=root['receiptRef'],priorPlanRef=root['planRef'],
            requirementRef=self._json(requirement_ref),fulfillmentRef=self._json(fulfillment_ref),
            checkpointRef=self._json(route.requirement.checkpoint_ref),
            sourceReadinessRef=self._json(readiness_ref),evidenceRefs=[self._json(bundle_ref)],
            observedAt=observed_at,businessEvidenceRef=self._json(business_ref),
            readinessPolicyRef=self._json(current.refs[5]))
        command['requestHash']=_analysis_command_hash(command)
        context=AnalysisSnapshotResumeContext(fulfillment,
            AnalysisContinuationOrigin(AnalysisContinuationContext(self.analysis)))
        return _AnalysisSnapshotResumeSession(context,conn,command).resume()

    def _replay_committed(self, conn, route, current, root, requirement_ref, fulfillment):
        key=snapshot_route_key(self.analysis.scope,self._json(requirement_ref))
        saved=_HostAnalysisReceiptStore(HostTransaction(conn),self.analysis.scope).read(key)
        if saved is None:
            return None
        bundles=saved.get('evidenceRefs')
        if type(bundles) is not list or len(bundles)!=1 or type(bundles[0]) is not dict:
            raise ValueError('committed snapshot bundle reference differs')
        bundle=InvestigationExactRef.model_validate(bundles[0])
        if bundle.resource_type!='EvidenceBundleRevision' or type(bundle.revision) is not int:
            raise ValueError('committed snapshot bundle reference differs')
        row=conn.execute('''SELECT content_hash,item_refs FROM aip_evidence_bundle_revision
            WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s''',
            (*self.analysis.scope.key,bundle.resource_id,bundle.revision)).fetchone()
        if (row is None or 'sha256:'+row['content_hash']!=bundle.content_hash
                or type(row['item_refs']) is not list or len(row['item_refs'])!=1
                or type(row['item_refs'][0]) is not dict):
            raise ValueError('committed snapshot bundle lineage differs')
        item=dict(row['item_refs'][0])
        if type(item.get('contentHash')) is not str:
            raise ValueError('committed snapshot business evidence differs')
        item['contentHash']='sha256:'+item['contentHash'].removeprefix('sha256:')
        business_ref=InvestigationExactRef.model_validate(item)
        return self._resume(conn,route,current,root,requirement_ref=requirement_ref,
            fulfillment_ref=InvestigationExactRef.model_validate(saved.get('fulfillmentRef')),
            readiness_ref=InvestigationExactRef.model_validate(saved.get('sourceReadinessRef')),
            bundle_ref=bundle,observed_at=saved.get('observedAt'),business_ref=business_ref,
            fulfillment=fulfillment)

    def _coordinate(self, conn, route, current):
        refs=current.refs
        source=AnalysisSnapshotSourceEvidence(self.analysis,store=self.store)
        quality=AnalysisSnapshotQualityEvidence(source)
        business=AnalysisSnapshotBusinessEvidence(source)
        readiness=AnalysisSnapshotReadiness(AnalysisSnapshotReadinessContext(business))
        brief=AnalysisSnapshotBrief(business)
        bundle=AnalysisSnapshotBundle(brief)
        fulfillment=AnalysisSnapshotFulfillment(bundle,readiness)
        root=_HostAnalysisReceiptStore(HostTransaction(conn),self.analysis.scope).read_exact(route.analysis_receipt_ref)
        if root is None or root.get('receiptRef')!=route.analysis_receipt_ref:
            raise ValueError('original analysis Receipt unavailable during coordination')
        requirement=route.requirement
        requirement_ref=InvestigationExactRef(resource_type='DataRequirementRevision',
            resource_id=requirement.requirement_id,revision=requirement.revision,
            content_hash=requirement.content_hash)
        committed=self._replay_committed(conn,route,current,root,requirement_ref,fulfillment)
        if committed is not None:
            return committed

        source_ref=source.capture_current(conn,receipt_ref=route.analysis_receipt_ref,
            policy_ref=refs[0],quality_ref=refs[1],cohort_ref=refs[2],field_ref=refs[3])
        query_ref=quality.query.execute_current(conn,evidence_ref=source_ref)
        quality_ref=quality.put_current(conn,evidence_ref=source_ref,query_ref=query_ref)
        business_ref=business.put_current(conn,evidence_ref=source_ref,query_ref=query_ref,
            quality_ref=quality_ref,policy_ref=refs[4])
        ready=readiness.put_current(conn,business_ref=business_ref,policy_ref=refs[5])
        bundle_ref=bundle.prepare_current(conn,business_ref=business_ref)
        fulfilled=fulfillment.put_current(conn,business_ref=business_ref,bundle_ref=bundle_ref,
            readiness_ref=ready.receipt_ref,policy_ref=refs[5])
        return self._resume(conn,route,current,root,requirement_ref=requirement_ref,
            fulfillment_ref=fulfillment.reference(fulfilled),
            readiness_ref=fulfilled.source_readiness_ref,bundle_ref=bundle_ref,
            observed_at=fulfilled.fulfilled_at.isoformat(),business_ref=business_ref,
            fulfillment=fulfillment)

    def run(self, *, route):
        scope=self.analysis.scope
        with self.analysis.connect(scope) as conn:
            self._validate_route(conn,route)
            current=self.policies.run_current(conn,scope=scope,
                refs=tuple(ref for ref,_ in route.group_bindings),actor=route.actor,
                execute=lambda value:value)
            conn.commit()
        self.completion.complete(scope=self.analysis.scope,group_id=route.group_id,actor=route.actor,
            bindings=route.group_bindings,policy_ref=current.refs[0])
        with self.analysis.connect(scope) as conn:
            self._validate_route(conn,route)
            result=self._coordinate(conn,route,current)
            def verify(latest):
                if latest != current:
                    raise ValueError('current installed policy set changed during coordination')
                return result
            result=self.policies.run_current(conn,scope=scope,
                refs=tuple(ref for ref,_ in route.group_bindings),actor=route.actor,execute=verify)
            conn.commit()
            return result
