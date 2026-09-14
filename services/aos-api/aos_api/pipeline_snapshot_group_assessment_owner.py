"""Bind relationship assessment to original input and current exported policy."""
from dataclasses import dataclass,replace
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_input_owner import CurrentSnapshotGroupInput,PipelineSnapshotGroupInputOwner
from aos_api.pipeline_snapshot_group_policy_owner import PipelineSnapshotGroupPolicyOwner
from aos_api.pipeline_snapshot_relationships import SnapshotRelationshipAssessment,assess_snapshot_relationships
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class CurrentSnapshotGroupAssessment:
    input: CurrentSnapshotGroupInput
    policy_ref: PipelineExactRef
    assessment: SnapshotRelationshipAssessment
    content_hash: str


def assessment_payload(current):
    """Canonical JSON-compatible preparation body, not a caller-issued receipt."""
    source=current.input
    return dict(schemaVersion='aos.snapshot-group-relationship-assessment/v1',
        tenant={'orgId':source.claim.scope.org_id,'projectId':source.claim.scope.project_id},
        groupId=source.claim.group_id,claimRequestHash=source.claim.request_hash,inputManifestHash=source.manifest_hash,
        policyRef=current.policy_ref.model_dump(mode='json',by_alias=True),policyHash=current.assessment.policy_hash,
        readStartedAt=source.read_started_at.isoformat(),readCompletedAt=source.read_completed_at.isoformat(),
        counts=current.assessment.counts,candidateLinks=[dict(link,source_updated_at=link['source_updated_at'].isoformat()) for link in current.assessment.candidate_links])


class PipelineSnapshotGroupAssessmentOwner:
    def __init__(self,*,claims):
        self._inputs=PipelineSnapshotGroupInputOwner(claims=claims)
        self._policies=PipelineSnapshotGroupPolicyOwner(controls=claims._controls)

    def run_current(self,conn,*,scope,group_id,actor,bindings,policy_ref,execute):
        return self._run(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,
            policy_ref=policy_ref,execute=execute,completed_read=False)

    def run_completed_current(self,conn,*,scope,group_id,actor,bindings,policy_ref,execute):
        return self._run(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,
            policy_ref=policy_ref,execute=execute,completed_read=True)

    def _run(self,conn,*,scope,group_id,actor,bindings,policy_ref,execute,completed_read):
        if not callable(execute):raise TypeError('synchronous assessment consumer required')
        def consume_input(source):
            def consume_policy(current):
                if current.group!=source.group:raise ValueError('policy and original input groups differ')
                outputs={mapping.read_spec.object_type:parent['outputRows'] for (_,_,mapping),parent in zip(source.group.members,source.parents)}
                assessment=assess_snapshot_relationships(outputs,current.policy,observed_at=source.read_completed_at)
                provisional=CurrentSnapshotGroupAssessment(source,current.policy_ref,assessment,'')
                bound=replace(provisional,content_hash=observed_rows_hash([assessment_payload(provisional)]))
                result=execute(bound);_reject_deferred(result)
                if observed_rows_hash([assessment_payload(bound)])!=bound.content_hash:
                    raise ValueError('bound relationship assessment changed during consumption')
                return result
            return self._policies.run_current(conn,scope=scope,refs=tuple(ref for ref,_ in bindings),actor=actor,
                policy_ref=policy_ref,execute=consume_policy)
        read=self._inputs.run_completed_current if completed_read else self._inputs.run_current
        return read(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,execute=consume_input)
