"""Revalidate persisted group authority inside original source/recovery transactions."""
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner, _member


def guard_snapshot_schedule_run(conn, *, scope, run_id, actor, control_ref, controls):
    PipelineScheduleControlOwner._identity(conn,scope)
    row=conn.execute('''SELECT r.schedule_id,m.group_id,c.definition_id
        FROM public.meta_schedule_run r
        LEFT JOIN public.pipeline_snapshot_schedule_member m
          ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        LEFT JOIN public.pipeline_snapshot_schedule_current_member c
          ON (c.org_id,c.project_id,c.schedule_id)=(r.org_id,r.project_id,r.schedule_id)
        WHERE r.org_id=%s AND r.project_id=%s AND r.id=%s''',(*scope.key,run_id)).fetchone()
    if row is None:raise LookupError('snapshot schedule run unavailable')
    if row['group_id'] is None:
        if row['definition_id'] is not None:
            raise ValueError('snapshot definition requires its original run claim')
        return
    owner=PipelineSnapshotScheduleClaimOwner(controls=controls)
    record=owner.read(conn,scope=scope,group_id=str(row['group_id']))
    request=record['request']
    if record['schemaVersion']=='aos.snapshot-schedule-claim/v1':
        if row['definition_id'] is not None:
            raise ValueError('snapshot definition cannot adopt legacy run claims')
        return
    member=next((item for item in record['members'] if item['runId']==run_id),None)
    ref=PipelineExactRef.model_validate(control_ref).model_dump(mode='json',by_alias=True,exclude_none=True)
    if request['actor']!=actor or member is None or member['controlRef']!=ref:
        raise ValueError('snapshot definition run control or actor differs')
    schedule_ids=tuple(m['scheduleId'] for m in request['members'])
    bindings=PipelineScheduleControlOwner.read_latest_many(conn,scope=scope,schedule_ids=schedule_ids)
    if any(b is None for b in bindings) or [_member(b) for b in bindings]!=request['members']:
        raise ValueError('snapshot definition original binding is not current')
    definition=owner._lock_definition(conn,scope,request['definitionRef'],bindings,actor)
    def validate(_group):
        schedules={r['id']:r for r in conn.execute('''SELECT id,pipeline_id,enabled,ingest FROM public.meta_schedule
            WHERE org_id=%s AND project_id=%s AND id=ANY(%s)
            ORDER BY id COLLATE "C" FOR UPDATE''',(*scope.key,list(schedule_ids))).fetchall()}
        members={r['schedule_id']:r for r in conn.execute('''SELECT schedule_id,definition_id,revision
            FROM public.pipeline_snapshot_schedule_current_member
            WHERE org_id=%s AND project_id=%s AND schedule_id=ANY(%s)''',
            (*scope.key,list(schedule_ids))).fetchall()}
        latest=PipelineScheduleControlOwner.read_latest_many(conn,scope=scope,schedule_ids=schedule_ids)
        for binding,current_binding in zip(bindings,latest):
            schedule=schedules.get(binding.schedule_id)
            current=members.get(binding.schedule_id)
            if (current is None or str(current['definition_id'])!=definition['definitionId']
                    or current['revision']!=definition['revision']
                    or schedule is None or schedule['enabled'] is not True
                    or schedule['pipeline_id']!=binding.pipeline_id
                    or type(schedule['ingest']) is not dict
                    or schedule['ingest'].get('kind')!='pipeline-live-v1'
                    or schedule['ingest'].get('pipelineId')!=binding.pipeline_id
                    or current_binding!=binding):
                raise ValueError('snapshot definition current member authority differs')
    owner._groups.run_current(conn,scope=scope,actor=actor,
        refs=tuple(b.control_ref for b in bindings),execute=validate)


def guard_single_snapshot_prepare(conn, *, scope, run_id):
    PipelineScheduleControlOwner._identity(conn,scope)
    grouped=conn.execute('''SELECT 1 FROM public.meta_schedule_run r
        LEFT JOIN public.pipeline_snapshot_schedule_member m
          ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
        LEFT JOIN public.pipeline_snapshot_schedule_current_member c
          ON (c.org_id,c.project_id,c.schedule_id)=(r.org_id,r.project_id,r.schedule_id)
        WHERE r.org_id=%s AND r.project_id=%s AND r.id=%s
          AND (m.group_id IS NOT NULL OR c.definition_id IS NOT NULL)''',(*scope.key,run_id)).fetchone()
    if grouped is not None:
        raise ValueError('snapshot group requires whole-group source preparation')


def guard_snapshot_schedule_group(conn, *, scope, group_id, actor, bindings, controls):
    PipelineScheduleControlOwner._identity(conn,scope)
    groups=conn.execute('''SELECT DISTINCT group_id FROM public.pipeline_snapshot_schedule_member
        WHERE org_id=%s AND project_id=%s AND run_id=ANY(%s)''',
        (*scope.key,[run for _,run in bindings])).fetchall()
    if not groups:return
    if len(groups)!=1 or str(groups[0]['group_id'])!=group_id:
        raise ValueError('snapshot definition original group identity differs')
    record=PipelineSnapshotScheduleClaimOwner(controls=controls).read(conn,scope=scope,group_id=group_id)
    expected={m['runId']:m['controlRef'] for m in record['members']}
    actual={run:ref.model_dump(mode='json',by_alias=True,exclude_none=True) for ref,run in bindings}
    if record['request']['actor']!=actor or actual!=expected:
        raise ValueError('snapshot definition requires complete original group bindings')
