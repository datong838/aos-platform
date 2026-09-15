"""Six current installed snapshot policies; no source read or resume grant."""
from dataclasses import dataclass

from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_business_facts import compile_business_fact_policy
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy
from aos_api.pipeline_snapshot_group_policy_owner import PipelineSnapshotGroupPolicyOwner
from aos_api.pipeline_snapshot_readiness_policy import compile_snapshot_readiness_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy


@dataclass(frozen=True)
class AnalysisSnapshotPolicySet:
    refs: tuple
    relationship: object
    quality: object
    cohort: object
    fields: object
    business: object
    readiness: object


class AnalysisSnapshotPolicySetOwner:
    POLICIES = (
        ('SnapshotRelationshipPolicy', 'content/policies/snapshot-relationships.v1.json'),
        ('SnapshotRelationshipQualityPolicy', 'content/policies/relationship-quality.v1.json'),
        ('SnapshotBusinessCohortPolicy', 'content/policies/business-cohort.v1.json'),
        ('SnapshotFactQualityPolicy', 'content/policies/fact-quality.v1.json'),
        ('SnapshotBusinessFactPolicy', 'content/policies/business-facts.v1.json'),
        ('SnapshotReadinessPolicy', 'content/policies/snapshot-readiness.v1.json'),
    )

    def __init__(self, *, controls):
        self._policies = PipelineSnapshotGroupPolicyOwner(controls=controls)

    def run_current(self, conn, *, scope, refs, actor, execute):
        if not callable(execute):
            raise TypeError('synchronous installed policy set consumer required')
        def consume(group):
            current=self._load(conn,scope,group)
            result=execute(current)
            _reject_deferred(result)
            if self._load(conn,scope,group)!=current:
                raise ValueError('current installed policy set changed during execution')
            return result
        return self._policies._groups.run_current(conn,scope=scope,refs=refs,actor=actor,execute=consume)

    def _load(self, conn, scope, group):
        refs=tuple(self._policies._resolve_exported_ref(conn,scope,group,
            resource_type=resource_type,path=path) for resource_type,path in self.POLICIES)
        if len({ref.revision for ref in refs})!=1 or refs[0].revision!=group.members[0][1].package_ref.version:
            raise ValueError('one current package version must own all snapshot policies')
        relationship=self._policies._load(conn,scope,group,refs[0])
        load=self._policies._load_exported_document
        quality=compile_relationship_quality_policy(load(conn,scope,group,refs[1],
            resource_type=refs[1].resource_type),relationship_policy=relationship)
        cohort=compile_business_cohort_policy(load(conn,scope,group,refs[2],
            resource_type=refs[2].resource_type),relationship_policy=relationship)
        fields=compile_fact_quality_policy(load(conn,scope,group,refs[3],
            resource_type=refs[3].resource_type),relationship_policy=relationship,
            cohort_policy=cohort,quality_policy=quality)
        business=compile_business_fact_policy(load(conn,scope,group,refs[4],
            resource_type=refs[4].resource_type),field_policy=fields)
        readiness=compile_snapshot_readiness_policy(load(conn,scope,group,refs[5],
            resource_type=refs[5].resource_type),field_policy=fields,quality_policy=quality)
        return AnalysisSnapshotPolicySet(refs,relationship,quality,cohort,fields,business,readiness)
