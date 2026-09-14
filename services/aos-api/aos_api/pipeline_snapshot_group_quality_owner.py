"""Current installed purpose coverage over original group inputs, read-only.

The returned record is evidence, never a saved authorization or fulfillment.
Consumers needing current authority must execute within run_current.
"""
from dataclasses import dataclass, replace

from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_assessment_owner import (
    CurrentSnapshotGroupAssessment, PipelineSnapshotGroupAssessmentOwner,
)
from aos_api.pipeline_snapshot_relationship_quality import (
    SnapshotRelationshipQualityMeasurement, compile_relationship_quality_policy,
    measure_relationship_quality,
)
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class CurrentSnapshotGroupQuality:
    assessment: CurrentSnapshotGroupAssessment
    quality_ref: PipelineExactRef
    measurement: SnapshotRelationshipQualityMeasurement
    content_hash: str


def quality_payload(current):
    original = current.assessment.input
    measurement = current.measurement
    return dict(schemaVersion='aos.snapshot-group-relationship-quality/v1',
        tenant=dict(orgId=original.claim.scope.org_id, projectId=original.claim.scope.project_id),
        groupId=original.claim.group_id, inputManifestHash=original.manifest_hash,
        assessmentHash=current.assessment.content_hash,
        readStartedAt=original.read_started_at.isoformat(), readCompletedAt=original.read_completed_at.isoformat(),
        relationshipPolicyRef=current.assessment.policy_ref.model_dump(mode='json', by_alias=True),
        qualityPolicyRef=current.quality_ref.model_dump(mode='json', by_alias=True),
        relationshipPolicyHash=measurement.relationship_policy_hash, qualityPolicyHash=measurement.quality_policy_hash,
        counts=measurement.counts, purposes=measurement.purposes)


class PipelineSnapshotGroupQualityOwner:
    def __init__(self, *, claims):
        self._assessments = PipelineSnapshotGroupAssessmentOwner(claims=claims)

    def run_current(self, conn, *, scope, group_id, actor, bindings, policy_ref, quality_ref, execute):
        if not callable(execute):
            raise TypeError('synchronous quality consumer required')
        quality_ref = PipelineExactRef.model_validate(quality_ref)
        def consume(assessment):
            source = assessment.input
            policies = self._assessments._policies
            relationship = policies._load(conn, scope, source.group, assessment.policy_ref)
            def load_quality():
                document = policies._load_exported_document(conn, scope, source.group, quality_ref,
                    resource_type='SnapshotRelationshipQualityPolicy')
                return compile_relationship_quality_policy(document, relationship_policy=relationship)
            quality = load_quality()
            outputs = {mapping.read_spec.object_type:parent['outputRows']
                for (_, _, mapping), parent in zip(source.group.members, source.parents)}
            measurement = measure_relationship_quality(outputs, relationship, quality,
                observed_at=source.read_completed_at)
            current = CurrentSnapshotGroupQuality(assessment, quality_ref, measurement, '')
            current = replace(current, content_hash=observed_rows_hash([quality_payload(current)]))
            result = execute(current)
            _reject_deferred(result)
            if load_quality() != quality or observed_rows_hash([quality_payload(current)]) != current.content_hash:
                raise ValueError('current group quality changed during consumption')
            return result
        return self._assessments.run_current(conn, scope=scope, group_id=group_id, actor=actor,
            bindings=bindings, policy_ref=policy_ref, execute=consume)
