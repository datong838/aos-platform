"""One-shot natural Cron observer for Q Policy12."""
import argparse
from datetime import datetime,timezone
import json
from time import monotonic,sleep

import a0v_l_natural_product_event as base
import a0v_q_successor_business as current

STATE=current.STATE.parent/'natural-product-event-v6'
POLICY_REVISION=12
EXPECTED_BINDING_REVISION=1
EXPECTED_GROUP_REVISION=55
INITIAL_TIMEOUT_SECONDS=1200


def configure():
    current.L_ID=current.Q_ID;current.L_GENERATION=current.Q_GENERATION
    base.current=current;base.STATE=STATE;base.POLICY_REVISION=POLICY_REVISION
    base.EXPECTED_BINDING_REVISION=EXPECTED_BINDING_REVISION
    base.validate_ready=validate_ready


def validate_ready(value,*,require_drained=True):
    schedule,policy,binding,routes=(value[key] for key in ('schedule','policy','binding','routes'))
    if (schedule is None or schedule['cron']!='0 * * * *'
        or schedule['pipeline_id']!='P02-product-qyh'
        or schedule['ingest']!={'kind':'pipeline-live-v1','pipelineId':'P02-product-qyh'}
        or policy is None or policy['current_revision']!=POLICY_REVISION or policy['enabled'] is not False
        or binding is None or binding['policy_revision']!=POLICY_REVISION
        or str(binding['installation_id'])!=current.Q_ID
        or str(binding['generation'])!=current.Q_GENERATION or binding['execution_epoch']!=3
        or binding['approved'] is not True or binding['enabled'] is not True
        or binding['revision']!=EXPECTED_BINDING_REVISION
        or binding['effective_until']<=datetime.now(timezone.utc)
        or len(routes)!=10 or [row['operation_id'] for row in routes]!=value['expectedOperations']
        or any(row['handler_kind']!='extension' or str(row['installation_id'])!=current.Q_ID
               or str(row['generation'])!=current.Q_GENERATION or row['execution_epoch']!=3
               or row['operation_fence'] is not False
               or row['cutover_group_revision']!=EXPECTED_GROUP_REVISION for row in routes)
        or (require_drained and value['inflight']!={'running':0,'unresolved':0})
        or any(count<0 for count in value['inflight'].values())
        or value['negativeCanaryDispatch']!=0):
        raise ValueError('exact Q natural Product window required')
    return value


def run(phase):
    if phase not in {'arm','observe','disarm','recover','watch'}:raise ValueError('unsupported Q natural-window phase')
    configure()
    if phase=='watch':return watch()
    if phase=='recover':return recover()
    result=getattr(base,phase)();result['outcome']=result['outcome'].replace('L_','Q_POLICY12_',1)
    return result


def _validate_recovery(value):
    validate_ready(value)
    runs,ingress=value['runs'],value['ingress']
    if (value['schedule']['enabled'] is not False or len(runs)!=1 or len(ingress)!=1
        or runs[0]['status']!='succeeded' or runs[0]['trigger']!='cron'
        or runs[0]['id']!=ingress[0]['run_id'] or value['occurrences']
        or value['attempts'] or value['investigationRuns']):
        raise ValueError('exact failed natural candidate recovery required')
    return value


def recover():
    base._private('arm-intent.json');base._private('disarm-intent.json')
    intent=STATE/'recovery-intent.json'
    if intent.exists():raise ValueError('existing recovery intent requires read-only observation')
    before=_validate_recovery(base.snapshot())
    material={'scheduleId':base.SCHEDULE,'policyId':base.POLICY,'policyRevision':POLICY_REVISION,
      'installationId':current.Q_ID,'generation':current.Q_GENERATION,
      'runId':before['runs'][0]['id'],'sourceRevision':before['ingress'][0]['source_revision'],
      'newSourceRunAllowed':False,'at':datetime.now(timezone.utc).isoformat()}
    base.freeze(intent,material)
    status,body=base.api('PATCH',f'/v1/schedules/{base.SCHEDULE}',{'enabled':True})
    after=base.snapshot()
    if (status!=200 or after['schedule']['enabled'] is not True
        or after['runs']!=before['runs'] or after['ingress']!=before['ingress']):
        raise ValueError('natural candidate recovery readback differs')
    result={'outcome':'Q_POLICY12_EXISTING_INGRESS_RECOVERY_ARMED','status':status,
      'body':body,'snapshot':after}
    base.freeze(STATE/'recovery-result.json',result)
    return result


def watch(*,initial_timeout_seconds=INITIAL_TIMEOUT_SECONDS,running_timeout_seconds=900,
          poll_seconds=5,clock=monotonic,pause=sleep):
    configure();base._private('arm-intent.json');deadline=clock()+initial_timeout_seconds
    extended=False
    while True:
        value=base.snapshot();validate_ready(value,require_drained=False);runs=value['runs']
        if len(runs)>1:raise ValueError('more than one natural run observed')
        terminal=runs[0] if runs and runs[0]['status'] in {'succeeded','failed'} else None
        downstream=bool(value['investigationRuns'])
        if terminal and (terminal['status']=='failed' or downstream):
            final=base.disarm()['snapshot']
            return {'outcome':'Q_POLICY12_NATURAL_TERMINAL_OBSERVED',
              'observedAt':datetime.now(timezone.utc).isoformat(),'terminalRun':terminal,
              'downstreamReady':downstream,'snapshot':final}
        if clock()>=deadline:
            if runs and runs[0]['status']=='running' and not extended:
                deadline=clock()+running_timeout_seconds;extended=True
            else:
                final=base.disarm()['snapshot']
                outcome=('Q_POLICY12_NATURAL_RUN_TERMINAL_TIMED_OUT' if runs and runs[0]['status']=='running'
                  else 'Q_POLICY12_NATURAL_DOWNSTREAM_TIMED_OUT' if terminal
                  else 'Q_POLICY12_NATURAL_WINDOW_TIMED_OUT')
                return {'outcome':outcome,'observedAt':datetime.now(timezone.utc).isoformat(),
                        'terminalRun':terminal,'snapshot':final}
        pause(poll_seconds)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['arm','observe','disarm','recover','watch']);args=parser.parse_args()
    print(json.dumps(run(args.phase),ensure_ascii=False,indent=2,default=str))
