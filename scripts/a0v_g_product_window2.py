"""Second exact G data window after the real model dependency successor."""
import argparse
import importlib.util
import json
import a0v_event_complete_successor_business as g
from a0v_g_model_successor_apply import load


def module(name):
    spec=importlib.util.spec_from_file_location('g_window2_'+name,g.ROOT/'scripts'/('a0v_event_complete_product_'+name+'.py'))
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    return p


def authority_profile():
    p=module('authority')
    previous=p.STATE
    p.STATE=g.STATE/'product-authority-v2';p.PREFIX='a0v-p02-g-authority-20260916-v2'
    p.previous_reference=lambda phase:load(previous/(phase+'-result.json'))['ref']
    return p


def policy_profile():
    p=module('policy');previous=p.STATE
    p.STATE=g.STATE/'product-event-v2';p.PREFIX='a0v-qyh-product-event-g-20260916-v2';p.authority=authority_profile()
    def predecessor():
        policy=load(previous/'prepare-result.json')['command']['policy']
        receipt=load(previous/'put-result.json')['receiptRef']
        if receipt['resourceId']!=p.POLICY or receipt['revision']!=3 or policy['revision']!=3 or receipt['contentHash']!=policy['contentHash']:
            raise ValueError('exact G policy3 predecessor required')
        return dict(policy,tenant=dict(orgId='org-org',projectId='dev-project'))
    p.previous_policy_payload=predecessor
    return p


def enable_profile():
    p=module('enable');p.STATE=g.STATE/'event-enable-v2';p.PREFIX='a0v-qyh-g-event-enable-20260916-v2'
    p.policy_profile=policy_profile
    return p


def source_profile():
    p=module('source_once');p.STATE=g.STATE/'product-source-v2';p.POLICY_REVISION=4
    p.authority_profile=authority_profile;p.policy_profile=policy_profile
    return p


def run(kind,phase):
    proof=load(g.STATE/'model-successor/verify-result.json')
    if proof.get('readiness')!='ready' or proof.get('coverage')!='complete' or proof.get('blockers'):
        raise ValueError('verified main model successor required')
    if kind=='source':
        if phase!='execute':raise ValueError('source execute only')
        return source_profile().run()
    allowed={'authority':('prepare','selection','control','binding'),'policy':('prepare','approve','put'),'enable':('approve-control','enable')}
    if kind not in allowed or phase not in allowed[kind]:raise ValueError('unsupported window phase')
    return globals()[kind+'_profile']().run(phase,g.setup())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=['authority','policy','enable','source']);parser.add_argument('phase');args=parser.parse_args()
    print(json.dumps(run(args.kind,args.phase),default=str))
