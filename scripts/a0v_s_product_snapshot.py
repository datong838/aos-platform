#!/usr/bin/env python3
"""Attach and execute one governed Product snapshot for recovered S."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os

import a0v_q_advisor_baseline as baseline
import a0v_qyh_current_product_event_first_chain as product


STATE = baseline.STATE / "s-product-snapshot-v2"
SELECTION_KEY = "a0v-p02-s-selection-20260917-v1"
CONTROL_KEY = "a0v-p02-s-control-20260917-v1"
BINDING_KEY = "a0v-p02-s-schedule-binding-20260917-v1"


def _load(name):
    path=STATE/f'{name}-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f'private S Product {name} result required')
    return json.loads(path.read_text())


def prepare(previous, preflight, plane):
    import a0v_s_successor_business as current
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.tenant_scope import TenantScope
    result=preflight.run('preflight')
    installation=result['currentInstallationRef']['installationId']
    scope=TenantScope(**baseline.SCOPE);services=plane.pipeline_control_factory.build(scope)
    with consumer_connection(runtime_worker_connection,baseline.SCOPE) as conn:
        selection=conn.execute("""SELECT * FROM pipeline_source_selection_revision
          WHERE org_id=%s AND project_id=%s AND pipeline_id=%s AND installation_id=%s
          ORDER BY created_at DESC LIMIT 1""",(*scope.key,product.PIPELINE,installation)).fetchone()
        control=conn.execute("""SELECT * FROM pipeline_runtime_control_revision
          WHERE org_id=%s AND project_id=%s AND pipeline_id=%s AND installation_id=%s
          ORDER BY created_at DESC LIMIT 1""",(*scope.key,product.PIPELINE,installation)).fetchone()
        binding=PipelineScheduleControlOwner(controls=services.controls).read_latest(
            conn,scope=scope,schedule_id=product.SCHEDULE)
        schedule=conn.execute("SELECT enabled FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s",
                              (*scope.key,product.SCHEDULE)).fetchone()
    if (result.get('outcome')!='PRODUCT_CURRENT_PREFLIGHT_GREEN'
        or binding is None or schedule is None or schedule['enabled'] is not False):
        raise RuntimeError('current disabled Product chain baseline required')
    if str(result['currentInstallationRef']['installationId'])!=current.S_ID:
        raise RuntimeError('exact S Product preflight required')
    return dict(outcome='S_PRODUCT_SNAPSHOT_PREPARED',draft=result['draft'],
        previousSelectionRef=None if selection is None else decode_selection_row(selection).ref.model_dump(mode='json',by_alias=True),
        previousControlRef=None if control is None else decode_control_row(control).ref.model_dump(mode='json',by_alias=True),
        previousBindingRef=binding.ref.model_dump(mode='json',by_alias=True),
        installationRef=result['currentInstallationRef'],runtimeBinding=result['runtimeBinding'])


def selection(_previous,_preflight,plane):
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.tenant_scope import TenantScope
    prepared=_load('prepare');scope=TenantScope(**baseline.SCOPE)
    ref=plane.pipeline_control_factory.build(scope).approve_selection(
        draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(prepared['draft'])),actor=baseline.ACTOR,
        idempotency_key=SELECTION_KEY,previous_ref=prepared['previousSelectionRef'])
    return dict(outcome='S_PRODUCT_SELECTION_APPROVED',ref=ref.model_dump(mode='json',by_alias=True))


def control(_previous,_preflight,plane):
    from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
    from aos_api.tenant_scope import TenantScope
    prepared=_load('prepare');selected=_load('selection')['ref'];scope=TenantScope(**baseline.SCOPE)
    draft={**prepared['draft'],'schemaVersion':'aos.pipeline-runtime-control-draft/v1',
           'sourceSelectionRef':selected}
    ref=plane.pipeline_control_factory.build(scope).approve_control(
        draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(draft)),actor=baseline.ACTOR,
        idempotency_key=CONTROL_KEY,previous_ref=prepared['previousControlRef'])
    return dict(outcome='S_PRODUCT_CONTROL_APPROVED',ref=ref.model_dump(mode='json',by_alias=True))


def binding(_previous,_preflight,plane):
    from aos_api.tenant_scope import TenantScope
    prepared=_load('prepare');controlled=_load('control')['ref'];scope=TenantScope(**baseline.SCOPE)
    ref=plane.pipeline_control_factory.build(scope).bind_schedule(
        pipeline_id=product.PIPELINE,schedule_id=product.SCHEDULE,control_ref=controlled,
        actor=baseline.ACTOR,idempotency_key=BINDING_KEY,
        previous_ref=prepared['previousBindingRef'])
    return dict(outcome='S_PRODUCT_SCHEDULE_BOUND',ref=ref.model_dump(mode='json',by_alias=True))


def execute(_previous,_preflight,_plane):
    status,enabled=product.api('PATCH',f'/v1/schedules/{product.SCHEDULE}',{'enabled':True})
    try:
        run_status,run=product.api('POST',f'/v1/schedules/{product.SCHEDULE}/run',{})
    finally:
        disabled_status,disabled=product.api('PATCH',f'/v1/schedules/{product.SCHEDULE}',{'enabled':False})
    if status!=200 or disabled_status!=200 or run_status not in (200,201) or run.get('status')!='succeeded':
        raise RuntimeError('S Product snapshot did not succeed')
    return dict(outcome='S_PRODUCT_SNAPSHOT_SUCCEEDED',enable=enabled,run=run,disable=disabled,
                rowsWritten=run.get('rowsWritten'),externalWrites=0)


def verify(previous,_preflight,_plane):
    prepared=_load('prepare');executed=_load('execute');iid=prepared['installationRef']['installationId']
    generation=prepared['runtimeBinding']['generation'];run_id=executed['run']['id']
    rows_written=(executed.get('rowsWritten') or executed['run'].get('lastRun',{}).get('rowsWritten')
                  or executed['run'].get('result',{}).get('rows_written'))
    with previous._scope_and_connection()[1] as conn:
        claim=conn.execute("""SELECT * FROM pipeline_controlled_source_claim WHERE org_id=%s
          AND project_id=%s AND run_id=%s""",(*baseline.SCOPE.values(),run_id)).fetchone()
        groups=conn.execute("""SELECT gi.group_id,gi.read_completed_at,count(*) OVER() AS group_count
          FROM pipeline_snapshot_group_input gi JOIN pipeline_snapshot_group_member gm
            ON gm.org_id=gi.org_id AND gm.project_id=gi.project_id AND gm.group_id=gi.group_id
          WHERE gi.org_id=%s AND gi.project_id=%s AND gm.run_id=%s""",
          (*baseline.SCOPE.values(),run_id)).fetchall()
        canary=conn.execute("SELECT count(*) AS n FROM pipeline_snapshot_group_input WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()['n']
    if (claim is None or str(claim['installation_id'])!=iid or str(claim['generation'])!=generation
        or claim['pipeline_id']!=product.PIPELINE or len(groups)!=1 or groups[0]['group_count']!=1
        or rows_written!=65 or canary!=0):
        raise RuntimeError('S governed Product snapshot differs')
    return dict(outcome='S_PRODUCT_GOVERNED_SNAPSHOT_GREEN',runId=run_id,rowsWritten=65,
        sourceClaim=dict(installationId=iid,generation=generation,controlId=str(claim['control_id']),
                         controlRevision=claim['control_revision']),
        snapshotGroup=dict(groupId=str(groups[0]['group_id']),readCompletedAt=groups[0]['read_completed_at']),
        canaryGroups=canary,verifiedAt=datetime.now(timezone.utc).isoformat())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','selection','control','binding','execute','verify'));args=parser.parse_args()
    output=STATE/f'{args.action}-result.json'
    if output.exists():raise RuntimeError('immutable S Product output exists')
    previous,preflight,plane=baseline.setup()
    result=globals()[args.action](previous,preflight,plane)
    baseline.freeze(output,result);print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':
    os.environ.setdefault('AOS_DOTENV_DISABLED','1');main()
