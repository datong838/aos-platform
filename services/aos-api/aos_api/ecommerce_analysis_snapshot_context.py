"""Original accepted analysis to its completed source group, without caller routing.

This is a read-only input bridge. Relationship coverage alone cannot fulfill a
DataRequirement or authorize analysis, capabilities, or external effects.
"""
from dataclasses import dataclass, replace
from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_locator import PipelineSnapshotGroupLocator
from aos_api.pipeline_snapshot_group_quality_owner import (
    CurrentSnapshotGroupQuality, PipelineSnapshotGroupQualityOwner, quality_payload,
)


@dataclass(frozen=True)
class CurrentAnalysisSnapshot:
    analysis_context: dict
    quality: CurrentSnapshotGroupQuality
    content_hash: str


def snapshot_context_payload(current):
    quality = quality_payload(current.quality)
    # CanonicalJson deliberately rejects tuples; serialize frozen purpose lists
    # without changing the Owner's in-memory measurement.
    quality['purposes'] = {code:{name:list(values) for name,values in entries.items()}
        for code,entries in quality['purposes'].items()}
    return dict(schemaVersion='aos.analysis-original-snapshot-context/v1',
        analysisContext=current.analysis_context, quality=quality)


class AnalysisSnapshotContext:
    def __init__(self, analysis):
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('original analysis service required')
        journal = analysis.source.reader._journal
        if (type(journal) is not ControlledIngressJournal or not journal._completed_read
            or journal._scope != analysis.scope or journal._actor != analysis.source.actor):
            raise ValueError('original completed source journal required')
        self.analysis = analysis
        self._continuation = AnalysisContinuationContext(analysis)
        self._locator = PipelineSnapshotGroupLocator(claims=journal._claims)
        self._quality = PipelineSnapshotGroupQualityOwner(claims=journal._claims)

    def run_current(self, conn, *, receipt_ref, policy_ref, quality_ref, execute):
        if not callable(execute):
            raise TypeError('synchronous original snapshot consumer required')
        def consume_analysis(context):
            origin = context['origin']
            journal = self.analysis.source.reader._journal
            if (origin['runId'] != journal._run_id or origin['actor'] != journal._actor
                or journal._actor != self.analysis.source.actor or not journal._completed_read
                or journal._scope != self.analysis.scope):
                raise ValueError('analysis origin differs from fixed completed source')
            cutoff = datetime.fromisoformat(context['analysisReceipt']['cutoffAt'])
            route = self._locator.read(conn,scope=self.analysis.scope,run_id=origin['runId'],expected_cutoff=cutoff)
            if route is None:
                raise LookupError('original analysis snapshot group unavailable')
            if route.actor != origin['actor'] or (journal._ref,origin['runId']) not in route.bindings:
                raise ValueError('analysis source control differs from original group')
            def consume_quality(quality):
                source = quality.assessment.input
                if (source.manifest_hash != route.manifest_hash or source.read_completed_at != cutoff
                    or context['source']['case']['analysisType'] not in quality.measurement.purposes):
                    raise ValueError('analysis snapshot or purpose differs')
                current = CurrentAnalysisSnapshot(context,quality,'')
                current = replace(current,content_hash=canonical_sha256(snapshot_context_payload(current)))
                result = execute(current)
                _reject_deferred(result)
                if canonical_sha256(snapshot_context_payload(current)) != current.content_hash:
                    raise ValueError('analysis snapshot context changed during consumption')
                return result
            return self._quality.run_completed_current(conn,scope=self.analysis.scope,
                group_id=route.group_id,actor=route.actor,bindings=route.bindings,
                policy_ref=policy_ref,quality_ref=quality_ref,execute=consume_quality)
        return self._continuation.run_current(conn,receipt_ref=receipt_ref,execute=consume_analysis)
