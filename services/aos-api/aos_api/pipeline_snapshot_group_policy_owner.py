"""Current installed policy around a complete current snapshot group, no write grant."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import PurePosixPath
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.extension_runtime.ipc import _pairs,_constant
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_owner import CurrentSnapshotGroup,PipelineSnapshotGroupOwner
from aos_api.pipeline_source_selection_owner import _now
from aos_api.pipeline_snapshot_relationships import SnapshotRelationshipPolicy,compile_relationship_policy
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v3 import SnapshotMappingV3


@dataclass(frozen=True)
class CurrentSnapshotGroupPolicy:
    group: CurrentSnapshotGroup
    policy_ref: PipelineExactRef
    policy: SnapshotRelationshipPolicy


class PipelineSnapshotGroupPolicyOwner:
    def __init__(self,*,controls):
        self._groups=PipelineSnapshotGroupOwner(controls=controls)
        self._selections=controls._selections

    def run_current(self,conn,*,scope,refs,actor,policy_ref,execute):
        policy_ref=PipelineExactRef.model_validate(policy_ref)
        path=PurePosixPath(policy_ref.resource_id)
        if (policy_ref.resource_type!='SnapshotRelationshipPolicy' or path.is_absolute()
                or any(part in {'.','..'} for part in path.parts) or str(path)!=policy_ref.resource_id
                or path.suffix!='.json' or not callable(execute)):
            raise ValueError('exact exported JSON relationship policy required')
        def consume(group):
            policy=self._load(conn,scope,group,policy_ref)
            current=CurrentSnapshotGroupPolicy(group,policy_ref,policy)
            result=execute(current);_reject_deferred(result)
            if self._load(conn,scope,group,policy_ref)!=policy:
                raise ValueError('current group policy changed during execution')
            return result
        return self._groups.run_current(conn,scope=scope,refs=refs,actor=actor,execute=consume)

    def _load(self,conn,scope,group,ref):
        document=self._load_exported_document(conn,scope,group,ref,resource_type='SnapshotRelationshipPolicy')
        policy=compile_relationship_policy(document)
        mappings={mapping.read_spec.object_type:mapping for _,_,mapping in group.members}
        if len(mappings)!=len(group.members) or set(mappings)!=set(policy.object_types):
            raise ValueError('policy requires exactly this complete object group')
        for rule in policy.rules:
            mapping=mappings[rule.row_type]
            if type(mapping) is SnapshotMappingV3 and mapping.public_projection is not None:
                fields=set(mapping.public_projection[1])
            else:
                base=mapping if type(mapping) is SnapshotMapping else mapping.base
                fields={target for _,target,_ in base.fields}|{key for key,_ in base.defaults}
            if rule.reference_property not in fields:raise ValueError('policy reference missing from current public output')
        return policy

    def _load_exported_document(self,conn,scope,group,ref,*,resource_type):
        """Internal loader: caller must remain inside this Owner's current group guard."""
        ref=PipelineExactRef.model_validate(ref)
        path=PurePosixPath(ref.resource_id)
        if (ref.resource_type!=resource_type or path.is_absolute()
                or any(part in {'.','..'} for part in path.parts) or str(path)!=ref.resource_id
                or path.suffix!='.json'):
            raise ValueError('exact exported JSON policy required')
        selections=self._selections;draft=group.members[0][1]
        if selections._artifacts.scope!=scope:raise PermissionError('artifact tenant differs')
        current=CurrentInstallationRef.model_validate(draft.installation_ref.model_dump(mode='json',by_alias=True))
        baseline=selections._store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,project_id=scope.project_id,requested_ref=current)
        package=draft.package_ref
        matches=[item for item in baseline.lock.payload.resolved if (item.publisher,item.id,item.version,item.content_hash)==(package.publisher,package.id,package.version,package.content_hash)]
        if len(matches)!=1:raise PermissionError('group policy package not uniquely installed')
        selected=matches[0]
        record=selections._artifacts.load_record(selected)
        selections._release_policy.evaluate(record,checked_at=_now(conn),expected_signature_fingerprint=selected.signature_fingerprint,expected_evidence_revision=selected.release_evidence_revision)
        if ref.revision!=selected.version or not ManifestLoader._is_exported_path(ref.resource_id,record.manifest.spec.exports.policies):
            raise PermissionError('policy is not the exact exported version')
        raw=selections._artifacts.read_artifact(selected,ref.resource_id,256*1024)
        if type(raw) is not bytes or len(raw)>256*1024 or 'sha256:'+hashlib.sha256(raw).hexdigest()!=ref.content_hash:
            raise ValueError('policy artifact digest differs')
        return json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant)
