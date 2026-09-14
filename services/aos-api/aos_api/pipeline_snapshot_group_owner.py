"""Compose existing current controls around one synchronous snapshot-group consumer."""
from dataclasses import dataclass
from datetime import datetime

from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner,_ref_identity
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2
from aos_api.pipeline_snapshot_materialization_v3 import SnapshotMappingV3
from aos_api.pipeline_source_selection_owner import _now
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class CurrentSnapshotGroup:
    members: tuple
    row_limit: int
    timeout_seconds: int
    not_before: datetime
    expires_at: datetime


class PipelineSnapshotGroupOwner:
    def __init__(self,*,controls):
        if type(controls) is not PipelineRuntimeControlOwner:raise TypeError('exact current control Owner required')
        self._controls=controls

    def run_current(self,conn,*,scope,refs,actor,execute):
        """No source call, claim or grant. Callback is trusted synchronous host code."""
        _require_transaction(conn)
        if type(scope) is not TenantScope or type(refs) is not tuple or not 1<=len(refs)<=12 or not callable(execute):
            raise ValueError('bounded exact group required')
        if type(actor) is not str or not actor.strip() or actor!=actor.strip() or len(actor)>240:
            raise ValueError('canonical group actor required')
        ordered=tuple(sorted((PipelineExactRef.model_validate(ref) for ref in refs),key=lambda ref:ref.resource_id))
        for ref in ordered:_ref_identity(ref,'PipelineRuntimeControlRevision','pipeline-control-')
        if len({ref.resource_id for ref in ordered})!=len(ordered):raise ValueError('unique group controls required')
        def walk(index,members,finish):
            if index==len(ordered):return finish(members)
            ref=ordered[index]
            return self._controls.run_current_snapshot(conn,scope=scope,ref=ref,actor=actor,
                execute=lambda draft,mapping:walk(index+1,members+((ref,draft,mapping),),finish))
        def consume(members):
            original=self._validate(conn,scope,members)
            result=execute(original)
            _reject_deferred(result)
            def verify(current):
                if self._validate(conn,scope,current)!=original:raise ValueError('current snapshot group changed during execution')
            walk(0,(),verify)
            return result
        return walk(0,(),consume)

    @staticmethod
    def _validate(conn,scope,members):
        common_fields=('org_id','project_id','installation_ref','generation','execution_epoch','configuration_ref',
            'package_ref','source_id','source_configuration_ref','schema_ref','masking_policy_ref')
        first=members[0][1];first_mapping=members[0][2]
        for _,draft,mapping in members:
            if type(draft) is not PipelineRuntimeControlDraft or type(mapping) not in (SnapshotMapping,SnapshotMappingV2,SnapshotMappingV3):
                raise ValueError('exact compiled group members required')
            if (draft.org_id,draft.project_id)!=scope.key or any(getattr(draft,name)!=getattr(first,name) for name in common_fields):
                raise ValueError('snapshot group authority differs')
            if (mapping.platform,mapping.shop_id)!=(first_mapping.platform,first_mapping.shop_id):
                raise ValueError('snapshot group business scope differs')
        if len({draft.pipeline_id for _,draft,_ in members})!=len(members):raise ValueError('unique pipelines required')
        if len({mapping.read_spec.table.casefold() for _,_,mapping in members})!=len(members):raise ValueError('unique source tables required')
        not_before=max(draft.not_before for _,draft,_ in members);expires_at=min(draft.expires_at for _,draft,_ in members)
        if not not_before<=_now(conn)<expires_at:raise PermissionError('snapshot group common window is not current')
        return CurrentSnapshotGroup(members,min(d.row_limit for _,d,_ in members),min(d.timeout_seconds for _,d,_ in members),not_before,expires_at)
