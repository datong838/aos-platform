"""P authority, Policy11, and event-control restoration for one natural Cron window."""
import argparse
import importlib.util
import json

import a0v_p_successor_business as current
import a0v_n_product_window as predecessor
from a0v_p_product_preflight import load_profile as preflight

current.G_ID=current.P_ID
current.G_GENERATION=current.P_GENERATION


def module(name):
    path=current.ROOT/'scripts'/f'a0v_event_complete_product_{name}.py'
    spec=importlib.util.spec_from_file_location(f'p_window_{name}',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    value.f=current
    return value


def _previous_ref(phase):
    if phase in {'selection','control'}:
        return None
    if phase!='binding':raise ValueError('unknown predecessor phase')
    ref=predecessor.authority_profile().load(phase)['ref']
    if (ref.get('resourceType')!='PipelineScheduleControlBinding' or ref.get('revision')!=16
        or ref.get('contentHash')!='sha256:d5d49ce2751b9355f40a7a67203de28517a7d56aaab29a0d6ef613625d7cf0f8'):
        raise ValueError('exact N authority predecessor required')
    return ref


def authority_profile():
    value=module('authority');value.STATE=current.STATE.parent/'product-authority-v5'
    value.PREFIX='a0v-p02-p-authority-20260917-v5'
    value.previous_reference=_previous_ref;value.preflight_profile=preflight
    return value


def policy_profile():
    value=module('policy');old=predecessor.policy_profile()
    value.STATE=current.STATE.parent/'product-event-v5'
    value.PREFIX='a0v-qyh-product-event-p-20260917-v5';value.authority=authority_profile()
    def previous():
        policy=old.load('prepare')['command']['policy'];receipt=old.load('put')['receiptRef']
        if (receipt['resourceId']!=value.POLICY or receipt['revision']!=10
            or policy['revision']!=10 or receipt['contentHash']!=policy['contentHash']
            or receipt['contentHash']!='sha256:3787b835eafc04830767b1cbcb92acfa6eceeb035eda0562f3dd5c326956d9e4'):
            raise ValueError('exact N Policy10 predecessor required')
        return dict(policy,tenant={'orgId':'org-org','projectId':'dev-project'})
    value.previous_policy_payload=previous
    return value


def enable_profile():
    value=module('enable');value.STATE=current.STATE.parent/'event-enable-v5'
    value.PREFIX='a0v-qyh-p-event-enable-20260917-v5'
    value.policy_profile=policy_profile;value.EXPECTED_GROUP_REVISION=48
    value.EXPECTED_BINDING_REVISION=0
    return value


def run(kind,phase):
    allowed={'authority':('prepare','selection','control','binding'),
      'policy':('prepare','approve','put'),
      'enable':('action','approve-dispatch','expand','approve-control','enable')}
    if kind not in allowed or phase not in allowed[kind]:
        raise ValueError('unsupported P natural-window phase')
    return globals()[kind+'_profile']().run(phase,current.setup())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['authority','policy','enable']);parser.add_argument('phase');args=parser.parse_args()
    print(json.dumps(run(args.kind,args.phase),ensure_ascii=False,default=str,indent=2))
