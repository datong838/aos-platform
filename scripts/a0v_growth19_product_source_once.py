"""One formal Product source run followed by bounded natural Host observation."""
import importlib.util
import json
import time
from datetime import datetime, timezone
import a0v_growth19_successor_business as f
from a0v_growth19_product_authority_window3 import load_profile as authority_profile
from a0v_growth19_product_event_policy_window3 import load_profile as policy_profile
from a0v_qyh_current_product_event_first_chain import api,freeze

STATE=f.STATE/'product-source-v3'


def counts():
    from a0v_formal_text_model_renewal import database_connect
    policy=policy_profile()
    with database_connect('aos_meta_head')() as c:
        occurrences=c.execute("SELECT status,count(*) AS n FROM automation_occurrence WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s GROUP BY status",(policy.POLICY,)).fetchall()
    return dict(at=datetime.now(timezone.utc).isoformat(),occurrences=[dict(r) for r in occurrences])


def run():
    if (STATE/'execute-intent.json').exists():raise ValueError('existing source intent requires read-only inspection')
    plane=f.setup();authority=authority_profile()
    from a0v_growth19_product_preflight import load_profile
    preflight=load_profile()
    spec=importlib.util.spec_from_file_location('f_source_observation',f.ROOT/'scripts/a0v_qyh_current_product_event_first_chain.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    current=previous.observe(preflight,plane)['current']
    if (current['schedule']['enabled'] is not False or current['binding']['ref']!=authority.load('binding')['ref']
        or current['binding']['controlRef']!=authority.load('control')['ref']):
        raise ValueError('exact disabled F source binding required')
    policy=policy_profile()
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as c:
        row=c.execute("SELECT enabled,approved,policy_revision,installation_id,generation,execution_epoch,effective_until>clock_timestamp() AS current FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s",(policy.POLICY,)).fetchone()
    if (row is None or not all(row[k] is True for k in ('enabled','approved','current'))
        or row['policy_revision']!=2 or str(row['installation_id'])!=f.F_ID
        or str(row['generation'])!=f.F_GENERATION or row['execution_epoch']!=3):
        raise ValueError('current approved F event binding required')
    freeze(STATE/'execute-intent.json',dict(scheduleId=authority.SCHEDULE,bindingRef=authority.load('binding')['ref'],maxSourceCalls=1,observationSeconds=180))
    result={}
    try:
        status,body=api('PATCH',f'/v1/schedules/{authority.SCHEDULE}',{'enabled':True})
        freeze(STATE/'schedule-enabled.json',dict(status=status,body=body))
        status,body=api('POST',f'/v1/schedules/{authority.SCHEDULE}/run',{})
        result=dict(status=status,body=body);freeze(STATE/'source-run-result.json',result)
        if body.get('status')!='succeeded':return result
        for index in range(12):
            snapshot=counts();freeze(STATE/f'observe-{index:02d}.json',snapshot)
            print(json.dumps(snapshot),flush=True)
            time.sleep(15)
        return result
    finally:
        status,body=api('PATCH',f'/v1/schedules/{authority.SCHEDULE}',{'enabled':False})
        freeze(STATE/'schedule-disabled.json',dict(status=status,body=body))


if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,default=str))
