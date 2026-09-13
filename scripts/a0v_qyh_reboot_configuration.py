"""Exact new-generation configuration after the recorded September 13 reboot."""
import argparse
import json
from a0v_qyh_reboot_recovery import STATE, KEY, PARENT, freeze, observe, validate_parent

INSTALLATION = '97aeb2e7-59ba-40f6-89a3-fb0293bc0497'
GENERATION = '3a445eee-aa28-4459-9e5a-f12a806a94b1'


def validate_candidate(snapshot, action):
    if action not in ('preflight', 'stage', 'configure', 'enable'):
        raise ValueError('unsupported configuration action')
    head = snapshot['head']
    if str(head['installation_id']) != INSTALLATION or head['state'] != 'active' or head['etag_version'] != 5:
        raise ValueError('exact recovery candidate required')
    bindings = snapshot['bindings']
    if len(bindings) != 1:
        raise ValueError('one recovery generation required')
    b = bindings[0]
    expected = (3, 2, 'unknown') if action == 'enable' else (1, 1, 'ready')
    if (str(b['generation']) != GENERATION or type(b['revision']) is not int
            or type(b['execution_epoch']) is not int
            or (b['revision'], b['execution_epoch'], b['observed_state']) != expected
            or b['enabled'] is not False or b['operation_fence'] is not True):
        raise ValueError('recovery candidate phase differs')
    if len(snapshot['resources']) != 3 or any(r['cleanup_state'] != 'pending' or r['observed_release'] is not False for r in snapshot['resources']):
        raise ValueError('live preparation resources required')
    if any(o['status'] != 'succeeded' for o in snapshot['operations']):
        raise ValueError('recovery operation has not succeeded')
    if snapshot['businessRoutes'] != 0 or snapshot['schedules']:
        raise ValueError('recovery candidate must have no business activity')


def run(action):
    from a0v_niushop_1_5_configure import load_profile
    profile = load_profile()
    profile.setup()
    validate_parent(observe(PARENT['installationId']), drained=True)
    validate_candidate(observe(INSTALLATION), action)
    def target(recovery=False, *, sleep_recovery=False, niushop_1_4=False):
        if any(flag is not False for flag in (recovery, sleep_recovery, niushop_1_4)):
            raise ValueError('only the fixed reboot recovery target is allowed')
        return INSTALLATION, STATE/'configuration.json', KEY, 'qyh-reboot'
    profile.configuration_target = target
    if action != 'preflight':
        freeze(STATE/(action+'-intent.json'), dict(installationId=INSTALLATION, generation=GENERATION, action=action))
    result = profile.run(action)
    freeze(STATE/(action+'-result.json'), result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('preflight', 'stage', 'configure', 'enable'))
    print(json.dumps(run(parser.parse_args().action), default=str, ensure_ascii=False, indent=2))
