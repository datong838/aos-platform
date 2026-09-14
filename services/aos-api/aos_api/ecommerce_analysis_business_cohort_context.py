"""Original requirement membership under current installed source policies.

Membership is neither field quality nor a fulfilled data requirement.
"""
from copy import deepcopy
from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_pending_data_context import AnalysisPendingDataContext
from aos_api.ecommerce_analysis_snapshot_context import AnalysisSnapshotContext
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy, select_business_cohort


class AnalysisBusinessCohortContext:
    def __init__(self, analysis):
        self._pending = AnalysisPendingDataContext(analysis)
        self._snapshot = AnalysisSnapshotContext(analysis)
        self.analysis = analysis

    def run_current(self, conn, *, receipt_ref, policy_ref, quality_ref, cohort_ref, execute):
        if not callable(execute):
            raise TypeError('synchronous business cohort consumer required')
        return self._run(conn,receipt_ref=receipt_ref,policy_ref=policy_ref,quality_ref=quality_ref,
            cohort_ref=cohort_ref,execute=lambda current,snapshot:execute(current))

    def _run(self, conn, *, receipt_ref, policy_ref, quality_ref, cohort_ref, execute):
        """Internal composition retains the original snapshot inside its guard."""
        if not callable(execute):
            raise TypeError('synchronous business cohort consumer required')
        cohort_ref = PipelineExactRef.model_validate(cohort_ref)
        def consume_pending(pending):
            def consume_snapshot(snapshot):
                if canonical_sha256(pending['analysisContext']) != canonical_sha256(snapshot.analysis_context):
                    raise ValueError('pending requirement and source analysis differ')
                requirement = pending['requirement']
                source = snapshot.quality.assessment.input
                if datetime.fromisoformat(requirement['cutoffAt']) != source.read_completed_at:
                    raise ValueError('business cutoff differs from original observation')
                policies = self._snapshot._quality._assessments._policies
                relationship = policies._load(conn,self.analysis.scope,source.group,snapshot.quality.assessment.policy_ref)
                def load():
                    document = policies._load_exported_document(conn,self.analysis.scope,source.group,cohort_ref,
                        resource_type='SnapshotBusinessCohortPolicy')
                    return compile_business_cohort_policy(document,relationship_policy=relationship)
                policy = load()
                if policy.purpose_code != requirement['purposeCode']:
                    raise ValueError('installed cohort purpose differs from original requirement')
                outputs = {mapping.read_spec.object_type:parent['outputRows']
                    for (_,_,mapping),parent in zip(source.group.members,source.parents)}
                selection = select_business_cohort(outputs,relationship,policy,
                    window_start=datetime.fromisoformat(requirement['timeWindow']['startAt']),
                    window_end=datetime.fromisoformat(requirement['timeWindow']['endAt']),
                    observed_at=source.read_completed_at)
                cohorts = {ot:dict(includedKeys=list(value.included_keys),
                    unknown=[dict(key=key,reasons=list(reasons)) for key,reasons in value.unknown],
                    excluded=[dict(key=key,reason=reason) for key,reason in value.excluded],
                    observedRows=value.observed_count,eligibleRows=value.eligible_count)
                    for ot,value in selection.cohorts.items()}
                current = dict(schemaVersion='aos.analysis-original-business-cohort/v1',
                    pendingContextHash=canonical_sha256(pending),snapshotContextHash=snapshot.content_hash,
                    requirement=deepcopy(requirement),
                    cohortPolicyRef=cohort_ref.model_dump(mode='json',by_alias=True),
                    cohortPolicyHash=selection.policy_hash,cohorts=cohorts)
                digest = canonical_sha256(current)
                result = execute(current,snapshot)
                _reject_deferred(result)
                if load() != policy or canonical_sha256(current) != digest:
                    raise ValueError('original business cohort changed during consumption')
                return result
            return self._snapshot.run_current(conn,receipt_ref=receipt_ref,policy_ref=policy_ref,
                quality_ref=quality_ref,execute=consume_snapshot)
        return self._pending.run_current(conn,receipt_ref=receipt_ref,execute=consume_pending)
