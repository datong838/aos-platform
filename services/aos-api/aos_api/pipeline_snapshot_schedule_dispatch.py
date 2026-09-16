"""Read-only cron routing; candidates never authorize source or Store effects."""
from datetime import UTC,datetime
from uuid import NAMESPACE_URL,uuid5
from zoneinfo import ZoneInfo

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner,_group_id
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.qyh_cron_scheduler import cron_matches
from aos_api.tenant_scope import TenantScope


def snapshot_slot_group_id(scope,definition_id,scheduled_for):
    if type(scope) is not TenantScope:raise TypeError('exact dispatch tenant required')
    definition_id=_group_id(definition_id)
    if (type(scheduled_for) is not datetime or scheduled_for.utcoffset() is None
            or scheduled_for.second or scheduled_for.microsecond):
        raise ValueError('aware canonical dispatch minute required')
    return str(uuid5(NAMESPACE_URL,'aos:snapshot-dispatch:'+canonical_sha256(
        [*scope.key,definition_id,scheduled_for.astimezone(UTC).isoformat()])))


class PipelineSnapshotScheduleDispatch:
    def __init__(self,*,definitions,claims):
        if (type(definitions) is not PipelineSnapshotScheduleDefinitionOwner
                or type(claims) is not PipelineSnapshotScheduleClaimOwner
                or definitions._groups is None
                or definitions._groups._groups._controls is not claims._groups._controls):
            raise TypeError('shared original dispatch Owners required')
        self._definitions,self._claims=definitions,claims

    def inspect(self,conn,*,scope,definition_id,now):
        if type(now) is not datetime or now.utcoffset() is None:
            raise ValueError('aware dispatch clock required')
        slot=now.astimezone(UTC).replace(second=0,microsecond=0)
        candidate=snapshot_slot_group_id(scope,definition_id,slot)
        definition=self._definitions.read(conn,scope=scope,definition_id=definition_id)
        if definition is None:raise LookupError('snapshot definition unavailable')
        body=definition['body']
        base=dict(executionAuthorized=False,definitionRef=definition['ref'],scheduledFor=slot.isoformat())
        if body['state']!='enabled':return dict(base,status=body['state'])
        # The aggregate is only a routing filter. Any selected original claim
        # is decoded by its original Owner before exposing the group identity.
        rows=conn.execute('''SELECT c.group_id,c.scheduled_for,
                count(r.id) FILTER (WHERE r.status='succeeded' AND r.executor_id='ec-live-v1'
                    AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL) AS completed
            FROM public.pipeline_snapshot_schedule_claim c
            LEFT JOIN public.pipeline_snapshot_schedule_member m
                ON (m.org_id,m.project_id,m.group_id)=(c.org_id,c.project_id,c.group_id)
            LEFT JOIN public.meta_schedule_run r
                ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
            WHERE c.org_id=%s AND c.project_id=%s AND c.request->'definitionRef'->>'resourceId'=%s
            GROUP BY c.group_id,c.scheduled_for
            HAVING count(r.id) FILTER (WHERE r.status='succeeded' AND r.executor_id='ec-live-v1'
                AND r.executor_stopped IS TRUE AND r.finished_at IS NOT NULL)<>12 OR c.scheduled_for=%s
            ORDER BY c.scheduled_for,c.group_id''',
            (*scope.key,definition['ref']['resourceId'],slot)).fetchall()
        pending=[];same=[]
        for row in rows:
            original=self._claims.read(conn,scope=scope,group_id=str(row['group_id']))
            if original is None:raise ValueError('dispatch original claim disappeared')
            group_id=original['request']['groupId']
            if row['completed']!=12:pending.append(group_id)
            elif row['scheduled_for']==slot:same.append(group_id)
        if pending:return dict(base,status='original_group_pending',groupIds=pending)
        if same:return dict(base,status='slot_completed',groupIds=same)
        row=conn.execute('''SELECT request FROM public.pipeline_snapshot_schedule_definition_revision
            WHERE org_id=%s AND project_id=%s AND definition_id=%s AND revision=%s''',
            (*scope.key,definition_id,body['revision'])).fetchone()
        if row['request'].get('intent')=='renew_saved_group':return dict(base,status='recovery_only')
        if not cron_matches(body['cron'],slot.astimezone(ZoneInfo(body['timezone']))):
            return dict(base,status='not_due')
        return dict(base,status='due',groupId=candidate,actor=body['executor'])
