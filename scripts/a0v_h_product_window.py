"""One real H product window with the exact G Policy4 predecessor."""
import argparse
import importlib.util
import json
import a0v_diagnostic_successor_business as h
import a0v_g_product_window2 as predecessor
from a0v_g_model_successor_apply import load
from a0v_h_product_preflight import load_profile as preflight


def module(name):
    spec=importlib.util.spec_from_file_location('h_window_'+name,h.ROOT/'scripts'/('a0v_event_complete_product_'+name+'.py'))
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p);p.f=h
    return p


def authority_profile():
    p=module('authority')
    p.STATE=h.STATE/'product-authority-v2';p.PREFIX='a0v-p02-h-authority-20260916-v2'
    p.previous_reference=lambda phase:None;p.preflight_profile=preflight
    return p


def policy_profile():
    p=module('policy');old=predecessor.policy_profile()
    p.STATE=h.STATE/'product-event';p.PREFIX='a0v-qyh-product-event-h-20260916-v1';p.authority=authority_profile()
    def previous():
        policy=old.load('prepare')['command']['policy'];receipt=old.load('put')['receiptRef']
        if receipt['resourceId']!=p.POLICY or receipt['revision']!=4 or policy['revision']!=4 or receipt['contentHash']!=policy['contentHash']:
            raise ValueError('exact G Policy4 predecessor required')
        return dict(policy,tenant=dict(orgId='org-org',projectId='dev-project'))
    p.previous_policy_payload=previous
    return p


def enable_profile():
    p=module('enable');p.STATE=h.STATE/'event-enable';p.PREFIX='a0v-qyh-h-event-enable-20260916-v1'
    p.policy_profile=policy_profile;p.EXPECTED_GROUP_REVISION=17
    return p


def source_profile():
    p=module('source_once');p.STATE=h.STATE/'product-source';p.POLICY_REVISION=5
    p.authority_profile=authority_profile;p.policy_profile=policy_profile;p.preflight_profile=preflight
    return p


def run(kind,phase):
    from a0v_h_current_binding_refresh import STATE as HEALTH
    proof=load(HEALTH/'result.json')
    if proof.get('readiness')!='ready' or proof.get('coverage')!='complete' or proof.get('blockers'):
        raise ValueError('current H model binding proof required')
    if kind=='source':
        if phase!='execute':raise ValueError('only one source execution allowed')
        return source_profile().run()
    allowed={'authority':('prepare','selection','control','binding'),'policy':('prepare','approve','put'),
             'enable':('approve-dispatch','expand','approve-control','enable')}
    if kind not in allowed or phase not in allowed[kind]:raise ValueError('unsupported H window phase')
    return globals()[kind+'_profile']().run(phase,h.setup())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['authority','policy','enable','source']);p.add_argument('phase');a=p.parse_args()
    print(json.dumps(run(a.kind,a.phase),default=str))
