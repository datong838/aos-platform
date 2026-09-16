"""L authority, Policy8, and event-control restoration for one natural Cron window."""
import argparse
import importlib.util
import json

import a0v_l_successor_business as current
import a0v_j_product_window as predecessor
from a0v_l_product_preflight import load_profile as preflight


# The reviewed reusable window modules use historical G_* names for the current
# installation. Keep the aliases local to this fixed executor profile.
current.G_ID = current.L_ID
current.G_GENERATION = current.L_GENERATION


def module(name):
    path = current.ROOT / 'scripts' / f'a0v_event_complete_product_{name}.py'
    spec = importlib.util.spec_from_file_location(f'l_window_{name}', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    value.f = current
    return value


def authority_profile():
    value = module('authority')
    value.STATE = current.STATE / 'product-authority'
    value.PREFIX = 'a0v-p02-l-authority-20260916-v1'
    value.previous_reference = lambda phase: None
    value.preflight_profile = preflight
    return value


def policy_profile():
    value = module('policy')
    old = predecessor.policy_profile()
    value.STATE = current.STATE / 'product-event'
    value.PREFIX = 'a0v-qyh-product-event-l-20260916-v1'
    value.authority = authority_profile()

    def previous():
        policy = old.load('prepare')['command']['policy']
        receipt = old.load('put')['receiptRef']
        if (receipt['resourceId'] != value.POLICY or receipt['revision'] != 7
            or policy['revision'] != 7 or receipt['contentHash'] != policy['contentHash']):
            raise ValueError('exact J Policy7 predecessor required')
        return dict(policy, tenant={'orgId': 'org-org', 'projectId': 'dev-project'})

    value.previous_policy_payload = previous
    return value


def enable_profile():
    value = module('enable')
    value.STATE = current.STATE / 'event-enable'
    value.PREFIX = 'a0v-qyh-l-event-enable-20260916-v1'
    value.policy_profile = policy_profile
    value.EXPECTED_GROUP_REVISION = 36
    return value


def run(kind, phase):
    allowed = {
        'authority': ('prepare', 'selection', 'control', 'binding'),
        'policy': ('prepare', 'approve', 'put', 'put-recovered'),
        'enable': ('action', 'approve-dispatch', 'expand', 'expand-recovered',
                   'approve-control', 'enable', 'enable-recovered'),
    }
    if kind not in allowed or phase not in allowed[kind]:
        raise ValueError('unsupported L natural-window phase')
    return globals()[kind + '_profile']().run(phase, current.setup())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['authority', 'policy', 'enable'])
    parser.add_argument('phase')
    args = parser.parse_args()
    print(json.dumps(run(args.kind, args.phase), ensure_ascii=False, default=str, indent=2))
