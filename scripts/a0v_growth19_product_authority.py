"""Receipt-first F source/control authority, with the existing schedule kept disabled."""
import argparse
import json
import a0v_growth19_successor_business as f

STATE=f.STATE/'product-authority'
PIPELINE='P02-product-qyh'
SCHEDULE='sch-p02-qyh-controlled-20260913-v1'
PREFIX='a0v-p02-f-authority-20260916-v1'


def load(phase):
    path=STATE/(phase+'-result.json')
    if path.stat().st_mode & 0o777!=0o600:raise ValueError('private result required')
    return json.loads(path.read_text())


def require_f(draft):
    if (draft['installationRef']['installationId']!=f.F_ID or draft['generation']!=f.F_GENERATION
        or draft['executionEpoch']!=3 or draft['configurationRef']!=f.CONFIG
        or draft['pipelineId']!=PIPELINE or draft['orgId']!='org-org' or draft['projectId']!='dev-project'):
        raise ValueError('exact F Product draft required')


def previous_reference(phase):
    return None


def run(phase,plane):
    from a0v_qyh_current_product_event_first_chain import freeze
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft,PipelineRuntimeControlDraft
    from aos_api.tenant_scope import TenantScope
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    scope=TenantScope('org-org','dev-project')
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing intent requires read-only inspection')
    if phase=='prepare':
        from a0v_growth19_product_preflight import load_profile
        result=load_profile().run('preflight');require_f(result['draft'])
        freeze(intent,dict(installationId=f.F_ID,generation=f.F_GENERATION))
    else:
        draft=load('prepare')['draft'];require_f(draft)
        service=plane.pipeline_control_factory.build(scope)
        if phase=='selection':
            material=dict(actor=f.ACTOR,idempotencyKey=PREFIX+'-selection',draft=draft,previousRef=previous_reference(phase))
            freeze(intent,material)
            ref=service.approve_selection(draft=PipelineSourceSelectionDraft.model_validate_json(json.dumps(draft)),actor=f.ACTOR,idempotency_key=material['idempotencyKey'],previous_ref=material['previousRef'])
        elif phase=='control':
            draft={**draft,'schemaVersion':'aos.pipeline-runtime-control-draft/v1','sourceSelectionRef':load('selection')['ref']}
            material=dict(actor=f.ACTOR,idempotencyKey=PREFIX+'-control',draft=draft,previousRef=previous_reference(phase))
            freeze(intent,material)
            ref=service.approve_control(draft=PipelineRuntimeControlDraft.model_validate_json(json.dumps(draft)),actor=f.ACTOR,idempotency_key=material['idempotencyKey'],previous_ref=material['previousRef'])
        elif phase=='binding':
            with consumer_connection(runtime_worker_connection,dict(org_id=scope.org_id,project_id=scope.project_id)) as conn:
                row=conn.execute('SELECT pipeline_id,enabled,ingest FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s',(*scope.key,SCHEDULE)).fetchone()
                if (row is None or row['pipeline_id']!=PIPELINE or row['enabled'] is not False
                    or row['ingest']!=dict(kind='pipeline-live-v1',pipelineId=PIPELINE)):
                    raise ValueError('exact disabled existing Product schedule required')
                if conn.execute("SELECT count(*) AS n FROM meta_schedule_run WHERE org_id=%s AND project_id=%s AND schedule_id=%s AND (status='running' OR executor_stopped IS NOT TRUE)",(*scope.key,SCHEDULE)).fetchone()['n']:
                    raise ValueError('previous Product execution not stopped')
                previous=PipelineScheduleControlOwner(controls=service.controls).read_latest(conn,scope=scope,schedule_id=SCHEDULE)
                if previous is None:raise ValueError('historical Product binding required')
                previous=previous.ref.model_dump(mode='json',by_alias=True)
                expected=previous_reference('binding')
                if expected is not None and expected!=previous:raise ValueError('renewal binding predecessor differs')
            material=dict(actor=f.ACTOR,idempotencyKey=PREFIX+'-binding',controlRef=load('control')['ref'],previousRef=previous)
            freeze(intent,material)
            ref=service.bind_schedule(pipeline_id=PIPELINE,schedule_id=SCHEDULE,control_ref=material['controlRef'],actor=f.ACTOR,idempotency_key=material['idempotencyKey'],previous_ref=previous)
        else:raise ValueError('unknown phase')
        result=dict(outcome='CURRENT_F_PRODUCT_'+phase.upper(),ref=ref.model_dump(mode='json',by_alias=True))
    freeze(STATE/(phase+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','selection','control','binding']);args=parser.parse_args()
    print(json.dumps(run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
