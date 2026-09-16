"""N authority, Policy10, and event-control restoration for one natural Cron window."""
import argparse
import importlib.util
import json

import a0v_n_successor_business as current
import a0v_l_product_window2 as predecessor
from a0v_n_product_preflight import load_profile as preflight

current.G_ID=current.N_ID
current.G_GENERATION=current.N_GENERATION


def module(name):
    path=current.ROOT/'scripts'/f'a0v_event_complete_product_{name}.py'
    spec=importlib.util.spec_from_file_location(f'n_window_{name}',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    value.f=current
    return value


def _previous_ref(phase):
    if phase in {'selection','control'}:
        return None
    if phase!='binding':raise ValueError('unknown predecessor phase')
    ref=predecessor.authority_profile().load(phase)['ref']
    if (ref.get('resourceType')!='PipelineScheduleControlBinding' or ref.get('revision')!=15
        or ref.get('contentHash')!='sha256:4a10238afafe0427726fa8b53506d0d082d5d794aca5c8819874628660516804'):
        raise ValueError('exact L v2 authority predecessor required')
    return ref


def authority_profile():
    value=module('authority');value.STATE=current.STATE.parent/'product-authority-v4'
    value.PREFIX='a0v-p02-n-authority-20260917-v4'
    value.previous_reference=_previous_ref;value.preflight_profile=preflight
    return value


def policy_profile():
    value=module('policy');old=predecessor.policy_profile()
    value.STATE=current.STATE.parent/'product-event-v4'
    value.PREFIX='a0v-qyh-product-event-n-20260917-v4';value.authority=authority_profile()
    def previous():
        policy=old.load('prepare')['command']['policy'];receipt=old.load('put')['receiptRef']
        if (receipt['resourceId']!=value.POLICY or receipt['revision']!=9
            or policy['revision']!=9 or receipt['contentHash']!=policy['contentHash']
            or receipt['contentHash']!='sha256:7f8b9655351a7f5b50ed8930f9b767926d76817194ee7225474c3ff2a26c95ed'):
            raise ValueError('exact L Policy9 predecessor required')
        return dict(policy,tenant={'orgId':'org-org','projectId':'dev-project'})
    value.previous_policy_payload=previous
    return value


def enable_profile():
    value=module('enable');value.STATE=current.STATE.parent/'event-enable-v4'
    value.PREFIX='a0v-qyh-n-event-enable-20260917-v4'
    value.policy_profile=policy_profile;value.EXPECTED_GROUP_REVISION=42
    value.EXPECTED_BINDING_REVISION=0
    return value


def run(kind,phase):
    allowed={'authority':('prepare','selection','control','binding'),
      'policy':('prepare','approve','put'),
      'enable':('action','approve-dispatch','expand','approve-control','enable')}
    if kind not in allowed or phase not in allowed[kind]:
        raise ValueError('unsupported N natural-window phase')
    return globals()[kind+'_profile']().run(phase,current.setup())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['authority','policy','enable']);parser.add_argument('phase');args=parser.parse_args()
    print(json.dumps(run(args.kind,args.phase),ensure_ascii=False,default=str,indent=2))
