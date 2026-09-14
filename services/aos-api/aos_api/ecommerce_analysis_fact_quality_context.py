"""Installed field counts over original pending data; no fulfilled authority."""
from copy import deepcopy
from datetime import datetime

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_business_cohort_context import AnalysisBusinessCohortContext
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy, measure_fact_quality


class AnalysisFactQualityContext:
    def __init__(self, analysis):
        self._business=AnalysisBusinessCohortContext(analysis)
        self.analysis=analysis

    def run_current(self, conn, *, receipt_ref, policy_ref, quality_ref, cohort_ref, field_ref, execute):
        if not callable(execute):raise TypeError('synchronous fact quality consumer required')
        field_ref=PipelineExactRef.model_validate(field_ref)
        def consume(business,snapshot):
            source=snapshot.quality.assessment.input
            policies=self._business._snapshot._quality._assessments._policies
            relationship=policies._load(conn,self.analysis.scope,source.group,snapshot.quality.assessment.policy_ref)
            quality=compile_relationship_quality_policy(policies._load_exported_document(
                conn,self.analysis.scope,source.group,snapshot.quality.quality_ref,
                resource_type='SnapshotRelationshipQualityPolicy'),relationship_policy=relationship)
            cohort=compile_business_cohort_policy(policies._load_exported_document(
                conn,self.analysis.scope,source.group,PipelineExactRef.model_validate(business['cohortPolicyRef']),
                resource_type='SnapshotBusinessCohortPolicy'),relationship_policy=relationship)
            def load():
                document=policies._load_exported_document(conn,self.analysis.scope,source.group,field_ref,
                    resource_type='SnapshotFactQualityPolicy')
                return compile_fact_quality_policy(document,relationship_policy=relationship,cohort_policy=cohort,quality_policy=quality)
            fields=load();requirement=business['requirement']
            if (len(requirement['requiredFacts'])!=len(fields.facts)
                or set(requirement['requiredFacts'])!={ot for ot,_ in fields.facts}):
                raise ValueError('field facts differ from original requirement')
            outputs={mapping.read_spec.object_type:parent['outputRows']
                for (_,_,mapping),parent in zip(source.group.members,source.parents)}
            measurement=measure_fact_quality(outputs,relationship,cohort,quality,fields,
                window_start=datetime.fromisoformat(requirement['timeWindow']['startAt']),
                window_end=datetime.fromisoformat(requirement['timeWindow']['endAt']),observed_at=source.read_completed_at)
            current=dict(schemaVersion='aos.analysis-original-fact-quality-context/v1',
                businessCohortHash=canonical_sha256(business),fieldPolicyRef=field_ref.model_dump(mode='json',by_alias=True),
                sourceObservedAt=source.read_completed_at.isoformat(),requirement=deepcopy(requirement),measurement=measurement)
            digest=canonical_sha256(current)
            result=execute(current)
            _reject_deferred(result)
            if load()!=fields or canonical_sha256(current)!=digest:
                raise ValueError('original field quality changed during consumption')
            return result
        return self._business._run(conn,receipt_ref=receipt_ref,policy_ref=policy_ref,quality_ref=quality_ref,
            cohort_ref=cohort_ref,execute=consume)
