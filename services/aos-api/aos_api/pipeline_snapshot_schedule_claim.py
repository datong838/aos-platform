"""Atomic schedule-run reservation, never a source-read authorization."""
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_schedule_claim import read_current_snapshot_definition
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner, ScheduleControlBinding
from aos_api.pipeline_snapshot_group_owner import PipelineSnapshotGroupOwner
from aos_api.pipeline_source_claim_owner import _text
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
from aos_api.tenant_scope import TenantScope


def _group_id(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError('canonical schedule group required')
    return value


def _member(binding):
    return dict(scheduleId=binding.schedule_id, pipelineId=binding.pipeline_id,
        bindingRef=binding.ref.model_dump(mode='json', by_alias=True, exclude_none=True),
        controlRef=binding.control_ref.model_dump(mode='json', by_alias=True, exclude_none=True))


class PipelineSnapshotScheduleClaimOwner:
    def __init__(self, *, controls):
        if type(controls) is not PipelineRuntimeControlOwner:
            raise TypeError('original runtime control Owner required')
        self._groups = PipelineSnapshotGroupOwner(controls=controls)

    def read(self, conn, *, scope, group_id):
        """Read immutable routing evidence only; callers must revalidate controls."""
        PipelineScheduleControlOwner._identity(conn, scope)
        group_id = _group_id(group_id)
        row = conn.execute('''SELECT request,request_hash,record,content_hash FROM public.pipeline_snapshot_schedule_claim
            WHERE org_id=%s AND project_id=%s AND group_id=%s''', (*scope.key, group_id)).fetchone()
        if row is None:
            return None
        record, request = row['record'], row['request']
        if (canonical_sha256(request) != row['request_hash'] or canonical_sha256(record) != row['content_hash']
                or record.get('schemaVersion') not in ('aos.snapshot-schedule-claim/v1','aos.snapshot-schedule-claim/v2')
                or set(record) != {'schemaVersion','request','members'} or record['request'] != request
                or (request.get('orgId'),request.get('projectId'),request.get('groupId')) != (*scope.key,group_id)
                or type(record['members']) is not list or len(record['members']) != 12
                or type(request.get('members')) is not list or len(request['members']) != 12):
            raise ValueError('saved snapshot schedule claim differs')
        version = record['schemaVersion'].rsplit('/',1)[1]
        fields = {'schemaVersion','orgId','projectId','groupId','actor','scheduledFor','trigger','members'}
        if version == 'v2': fields.add('definitionRef')
        if set(request) != fields or request.get('schemaVersion') != 'aos.snapshot-schedule-request/'+version:
            raise ValueError('saved snapshot schedule request version differs')
        if version == 'v2':
            self._definition_ref(request['definitionRef'])
        saved = conn.execute('''SELECT ordinal,schedule_id,binding_id,binding_revision,binding_hash,run_id
            FROM public.pipeline_snapshot_schedule_member WHERE org_id=%s AND project_id=%s AND group_id=%s
            ORDER BY ordinal''', (*scope.key,group_id)).fetchall()
        if len(saved) != 12:
            raise ValueError('saved snapshot schedule membership differs')
        for ordinal, (member, original, index) in enumerate(zip(record['members'],request['members'],saved),1):
            if (type(member) is not dict or set(member) != {'scheduleId','pipelineId','bindingRef','controlRef','runId'}
                    or {k:v for k,v in member.items() if k != 'runId'} != original
                    or (index['ordinal'], index['schedule_id'], index['run_id']) != (ordinal,member['scheduleId'],member['runId'])
                    or member['bindingRef'] != dict(resourceType='PipelineScheduleControlBinding',
                        resourceId='schedule-control-'+str(index['binding_id']), revision=index['binding_revision'],
                        contentHash=index['binding_hash'])):
                raise ValueError('saved snapshot schedule member differs')
        return deepcopy(record)

    @staticmethod
    def _definition_ref(value):
        ref=PipelineExactRef.model_validate(value)
        if ref.resource_type != 'SnapshotScheduleDefinitionRevision' or not ref.resource_id.startswith('snapshot-schedule-'):
            raise ValueError('exact snapshot definition reference required')
        identifier=_group_id(ref.resource_id.removeprefix('snapshot-schedule-'))
        return identifier,ref.model_dump(mode='json',by_alias=True,exclude_none=True)

    def _lock_definition(self,conn,scope,ref,bindings,actor):
        # Import at use time: the configuration Owner shares _member with this module.
        from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
        identifier,wire=self._definition_ref(ref)
        target=conn.execute("""SELECT installation_id FROM public.pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s""",(*scope.key,identifier)).fetchone()
        if target is None:raise ValueError('snapshot definition unavailable')
        if conn.execute("""SELECT installation_id FROM public.bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE""",
            (*scope.key,target['installation_id'])).fetchone() is None:
            raise ValueError('snapshot installation unavailable')
        conn.execute("""SELECT revision FROM public.pipeline_snapshot_schedule_definition_head
            WHERE org_id=%s AND project_id=%s AND definition_id=%s FOR UPDATE""",(*scope.key,identifier))
        row=conn.execute("""SELECT r.* FROM public.pipeline_snapshot_schedule_definition_revision r
            JOIN public.pipeline_snapshot_schedule_definition_head h
            ON (r.org_id,r.project_id,r.definition_id,r.revision,r.content_hash)=
               (h.org_id,h.project_id,h.definition_id,h.revision,h.content_hash)
            WHERE h.org_id=%s AND h.project_id=%s AND h.definition_id=%s""",(*scope.key,identifier)).fetchone()
        value=PipelineSnapshotScheduleDefinitionOwner._decode(row,scope,identifier)
        body=value['body']
        if (value['ref']!=wire or body['state']!='enabled' or body['executor']!=actor
                or body['members']!=[_member(b) for b in bindings]
                or any((b.installation_id,b.generation)!=(body['installationId'],body['generation']) for b in bindings)):
            raise ValueError('snapshot definition is not current enabled authority')
        return body

    def claim(self, conn, *, scope, group_id, actor, scheduled_for, trigger, bindings, definition_ref=None):
        PipelineScheduleControlOwner._identity(conn, scope)
        group_id, actor = _group_id(group_id), _text(actor,240)
        if type(scheduled_for) is not datetime or scheduled_for.utcoffset() is None:
            raise ValueError('aware schedule slot required')
        scheduled_for = scheduled_for.astimezone(UTC)
        if scheduled_for.second or scheduled_for.microsecond or trigger not in ('cron','manual'):
            raise ValueError('canonical schedule slot and trigger required')
        if (type(bindings) is not tuple or len(bindings) != 12
                or any(type(b) is not ScheduleControlBinding for b in bindings)):
            raise ValueError('complete twelve schedule bindings required')
        bindings = tuple(sorted(bindings,key=lambda b:b.schedule_id))
        if (len({b.schedule_id for b in bindings}) != 12
                or any(b.scope != scope or b.actor != actor for b in bindings)):
            raise PermissionError('schedule group actor or tenant differs')
        request = dict(schemaVersion='aos.snapshot-schedule-request/v1',orgId=scope.org_id,
            projectId=scope.project_id,groupId=group_id,actor=actor,scheduledFor=scheduled_for.isoformat(),
            trigger=trigger,members=[_member(b) for b in bindings])
        if definition_ref is not None:
            _,wire=self._definition_ref(definition_ref)
            request.update(schemaVersion='aos.snapshot-schedule-request/v2',definitionRef=wire)
        with conn.transaction():
            conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete,snapshot_schedule_member_complete DEFERRED')
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                ('snapshot-schedule:'+canonical_sha256([*scope.key,group_id]),))
            definition=(self._lock_definition(conn,scope,definition_ref,bindings,actor)
                        if definition_ref is not None else None)
            previous = self.read(conn,scope=scope,group_id=group_id)
            if previous is not None and previous['request'] != request:
                raise ValueError('snapshot schedule request differs')
            def reserve(group):
                canonical = {s.pipeline_id:s.object_type for s in CANONICAL_QYH_SOURCES}
                actual = {draft.pipeline_id:mapping.read_spec.object_type for _,draft,mapping in group.members}
                if actual != canonical or {b.pipeline_id for b in bindings} != set(canonical):
                    raise ValueError('complete canonical snapshot pipelines required')
                for binding in bindings:
                    schedule = conn.execute('''SELECT pipeline_id,enabled,ingest FROM public.meta_schedule
                        WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE''',
                        (*scope.key,binding.schedule_id)).fetchone()
                    if (schedule is None or schedule['enabled'] is not True
                            or schedule['pipeline_id'] != binding.pipeline_id
                            or type(schedule['ingest']) is not dict
                            or schedule['ingest'].get('kind') != 'pipeline-live-v1'
                            or schedule['ingest'].get('pipelineId') != binding.pipeline_id):
                        raise ValueError('snapshot member schedule is not enabled and bound')
                    membership=read_current_snapshot_definition(conn,scope,binding.schedule_id)
                    if definition is None:
                        if membership is not None:
                            raise ValueError('snapshot schedule requires its current definition authority')
                    elif membership is None or str(membership['definition_id'])!=definition['definitionId']:
                        raise ValueError('snapshot schedule current definition membership differs')
                    if PipelineScheduleControlOwner.read_latest(conn,scope=scope,schedule_id=binding.schedule_id) != binding:
                        raise ValueError('snapshot schedule binding is no longer current')
                if previous is not None:
                    conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete,snapshot_schedule_member_complete IMMEDIATE')
                    return previous
                now = conn.execute("SELECT date_trunc('minute',clock_timestamp()) AS slot").fetchone()['slot']
                if scheduled_for != now:
                    raise ValueError('new group requires the current schedule minute')
                members = []
                for binding in bindings:
                    if conn.execute('''SELECT 1 FROM public.meta_schedule_run WHERE org_id=%s AND project_id=%s
                        AND schedule_id=%s AND (status='running' OR executor_stopped IS NOT TRUE) LIMIT 1''',
                        (*scope.key,binding.schedule_id)).fetchone() is not None:
                        raise ValueError('snapshot member has an active or unconfirmed run')
                    run_id = 'scr-'+uuid4().hex
                    inserted = conn.execute('''INSERT INTO public.meta_schedule_run
                        (id,org_id,project_id,schedule_id,scheduled_for,trigger,status,started_at)
                        VALUES(%s,%s,%s,%s,%s,%s,'running',clock_timestamp())
                        ON CONFLICT(org_id,project_id,schedule_id,scheduled_for) DO NOTHING RETURNING id''',
                        (run_id,*scope.key,binding.schedule_id,scheduled_for,trigger)).fetchone()
                    if inserted is None:
                        raise ValueError('snapshot schedule slot already claimed')
                    members.append(dict(_member(binding),runId=run_id))
                record = dict(schemaVersion='aos.snapshot-schedule-claim/'+('v2' if definition else 'v1'),request=request,members=members)
                conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_claim
                    (org_id,project_id,group_id,actor,scheduled_for,trigger,request_hash,request,content_hash,record)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (*scope.key,group_id,actor,scheduled_for,trigger,canonical_sha256(request),Jsonb(request),
                     canonical_sha256(record),Jsonb(record)))
                for ordinal,(binding,member) in enumerate(zip(bindings,members),1):
                    conn.execute('''INSERT INTO public.pipeline_snapshot_schedule_member
                        (org_id,project_id,group_id,ordinal,schedule_id,binding_id,binding_revision,binding_hash,run_id)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (*scope.key,group_id,ordinal,binding.schedule_id,
                         binding.ref.resource_id.removeprefix('schedule-control-'),binding.ref.revision,
                         binding.ref.content_hash,member['runId']))
                conn.execute('SET CONSTRAINTS snapshot_schedule_claim_complete,snapshot_schedule_member_complete IMMEDIATE')
                return self.read(conn,scope=scope,group_id=group_id)
            return self._groups.run_current(conn,scope=scope,refs=tuple(b.control_ref for b in bindings),
                actor=actor,execute=reserve)
