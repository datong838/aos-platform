"""Principal-scoped configuration service; never creates runs or source calls."""
from contextlib import contextmanager
from copy import deepcopy
from aos_api.asset_registry.control_policy import validate_idempotency_key
from aos_api.pipeline_snapshot_schedule_claim import _group_id
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner,decode_binding
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.tenant_scope import TenantScope
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.asset_registry.manifest_loader import ManifestLoader


class PipelineSnapshotScheduleService:
    def __init__(self,*,scope,controls,installation_store):
        if type(scope) is not TenantScope:raise TypeError('exact tenant required')
        self.scope=scope
        self._owner=PipelineSnapshotScheduleDefinitionOwner(controls=controls,installation_store=installation_store)

    @contextmanager
    def _connection(self):
        tenant=dict(org_id=self.scope.org_id,project_id=self.scope.project_id)
        with consumer_connection(runtime_worker_connection,tenant) as conn:
            require_runtime_role(conn,**tenant,protected_tables=(
                'public.pipeline_snapshot_schedule_definition_revision',
                'public.pipeline_snapshot_schedule_definition_head',
                'public.pipeline_snapshot_schedule_current_member'))
            yield conn

    def configure(self,*,definition_id,actor,cron,policy_ref,members,expected_ref,idempotency_key):
        if type(members) not in (list,tuple) or len(members)!=12:
            raise ValueError('twelve exact schedule members required')
        with self._connection() as conn:
            bindings=[]
            for member in members:
                if type(member) is not dict or set(member)!={'scheduleId','bindingRef'}:
                    raise ValueError('exact schedule member required')
                current=PipelineScheduleControlOwner.read_latest(conn,scope=self.scope,schedule_id=member['scheduleId'])
                if current is None or current.ref!=PipelineExactRef.model_validate(member['bindingRef']):
                    raise ValueError('requested schedule binding is not current')
                bindings.append(current)
            return self._owner.configure(conn,scope=self.scope,definition_id=definition_id,actor=actor,
                cron=cron,policy_ref=policy_ref,bindings=tuple(bindings),expected_ref=expected_ref,idempotency_key=idempotency_key)

    def transition(self,*,definition_id,actor,intent,expected_ref,idempotency_key):
        with self._connection() as conn:
            return self._owner.transition(conn,scope=self.scope,definition_id=definition_id,actor=actor,
                intent=intent,expected_ref=expected_ref,idempotency_key=idempotency_key)

    def _read_authorized(self,conn,*,definition_id,actor):
        result=self._owner.read(conn,scope=self.scope,definition_id=definition_id)
        if result is None:raise LookupError('snapshot schedule definition unavailable')
        body=result['body']
        if self._owner._permission(conn,org_id=self.scope.org_id,project_id=self.scope.project_id,
                installation_id=body['installationId'],generation=body['generation'],actor=actor) is not True:
            raise PermissionError('current installation configuration permission required')
        return self._owner.read(conn,scope=self.scope,definition_id=definition_id)

    def read(self,*,definition_id,actor):
        with self._connection() as conn:
            return self._read_authorized(conn,definition_id=definition_id,actor=actor)

    def read_receipt(self,*,definition_id,actor,idempotency_key):
        definition_id=_group_id(definition_id)
        key=validate_idempotency_key(idempotency_key)
        with self._connection() as conn:
            self._read_authorized(conn,definition_id=definition_id,actor=actor)
            row=conn.execute('''SELECT * FROM public.pipeline_snapshot_schedule_definition_revision
                WHERE org_id=%s AND project_id=%s AND definition_id=%s AND idempotency_key=%s''',
                (*self.scope.key,definition_id,key)).fetchone()
            if row is None:raise LookupError('original snapshot schedule receipt unavailable')
            return dict(self._owner._decode(row,self.scope,definition_id),idempotencyKey=key,
                requestHash=row['request_hash'],request=deepcopy(row['request']))

    def list(self,*,actor,after=None,limit=50):
        if type(limit) is not int or not 1<=limit<=50:raise ValueError('page size must be 1 through 50')
        cursor=None if after is None else _group_id(after)
        with self._connection() as conn:
            rows=conn.execute('''SELECT definition_id FROM public.pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND (%s::uuid IS NULL OR definition_id>%s::uuid)
                ORDER BY definition_id LIMIT %s''',(*self.scope.key,cursor,cursor,limit+1)).fetchall()
            items=[self._read_authorized(conn,definition_id=str(row['definition_id']),actor=actor) for row in rows[:limit]]
            return dict(items=items,nextCursor=str(rows[limit-1]['definition_id']) if len(rows)>limit else None)

    def options(self,*,actor,installation_id,generation):
        installation_id,generation=_group_id(installation_id),_group_id(generation)
        policy_owner=self._owner._groups
        if policy_owner is None:raise PermissionError('source options unavailable in stop-only mode')
        with self._connection() as conn:
            if self._owner._permission(conn,org_id=self.scope.org_id,project_id=self.scope.project_id,
                    installation_id=installation_id,generation=generation,actor=actor) is not True:
                raise PermissionError('current configuration permission required')
            if conn.execute('''SELECT 1 FROM public.extension_runtime_binding WHERE org_id=%s AND project_id=%s
                AND installation_id=%s AND generation=%s''',(*self.scope.key,installation_id,generation)).fetchone() is None:
                raise LookupError('installation runtime generation unavailable')
            rows=conn.execute('''SELECT * FROM (SELECT DISTINCT ON(schedule_id) *
                FROM public.pipeline_schedule_control_binding WHERE org_id=%s AND project_id=%s
                ORDER BY schedule_id,revision DESC) latest WHERE installation_id=%s AND generation=%s''',
                (*self.scope.key,installation_id,generation)).fetchall()
            by_pipeline={source.pipeline_id:[] for source in CANONICAL_QYH_SOURCES}
            for row in rows:
                if row['pipeline_id'] in by_pipeline:by_pipeline[row['pipeline_id']].append(decode_binding(row))
            missing=[key for key,values in by_pipeline.items() if not values]
            ambiguous=[key for key,values in by_pipeline.items() if len(values)>1]
            result=dict(installationId=installation_id,generation=generation,status='incomplete',
                missing=missing,ambiguous=ambiguous,members=[],policies=[])
            if missing or ambiguous:return result
            bindings=self._owner._bindings(tuple(values[0] for values in by_pipeline.values()),self.scope)
            def resolve(group):
                if {draft.pipeline_id:mapping.read_spec.object_type for _,draft,mapping in group.members}!={source.pipeline_id:source.object_type for source in CANONICAL_QYH_SOURCES}:
                    raise ValueError('complete source mappings required')
                members=[]
                for binding in bindings:
                    row=conn.execute('''SELECT pipeline_id,ingest FROM public.meta_schedule
                        WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE''',(*self.scope.key,binding.schedule_id)).fetchone()
                    if row is None or row['pipeline_id']!=binding.pipeline_id or type(row['ingest']) is not dict or row['ingest'].get('kind')!='pipeline-live-v1' or row['ingest'].get('pipelineId')!=binding.pipeline_id:
                        raise ValueError('schedule mapping no longer current')
                    if PipelineScheduleControlOwner.read_latest(conn,scope=self.scope,schedule_id=binding.schedule_id)!=binding:
                        raise ValueError('schedule options changed during read')
                    occupied=conn.execute('''SELECT definition_id FROM public.pipeline_snapshot_schedule_current_member
                        WHERE org_id=%s AND project_id=%s AND schedule_id=%s''',(*self.scope.key,binding.schedule_id)).fetchone()
                    members.append(dict(scheduleId=binding.schedule_id,pipelineId=binding.pipeline_id,
                        bindingRef=binding.ref.model_dump(mode='json',by_alias=True,exclude_none=True),
                        controlRef=binding.control_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
                        definitionId=str(occupied['definition_id']) if occupied else None))
                _,record=policy_owner._current_release(conn,self.scope,group)
                paths=[]
                for artifact in record.artifacts:
                    path=artifact.get('relativePath') if type(artifact) is dict else getattr(artifact,'relative_path',None)
                    if type(path) is str and path.endswith('.json') and ManifestLoader._is_exported_path(path,record.manifest.spec.exports.policies):paths.append(path)
                if len(paths)>32 or len(set(paths))!=len(paths):raise ValueError('policy option set is not bounded and unique')
                policies=[]
                for path in sorted(paths):
                    # Other exported policy schemas may coexist. Only compiled
                    # relationship policies that cover this group are options.
                    ref=policy_owner._resolve_exported_ref(conn,self.scope,group,resource_type='SnapshotRelationshipPolicy',path=path)
                    try:policy_owner._load(conn,self.scope,group,ref)
                    except ValueError:continue
                    policies.append(ref.model_dump(mode='json',by_alias=True,exclude_none=True))
                return dict(result,status='ready' if policies else 'policy_unavailable',members=members,policies=policies)
            return policy_owner._groups.run_current(conn,scope=self.scope,refs=tuple(b.control_ref for b in bindings),actor=bindings[0].actor,execute=resolve)
