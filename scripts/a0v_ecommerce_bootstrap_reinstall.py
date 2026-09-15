"""Fixed I/event-complete profile; original A-H commands and receipts are retained."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID

os.environ.setdefault('AOS_DOTENV_DISABLED', '1')
ROOT = Path(__file__).resolve().parents[1]
OLD_STATE = ROOT.parent / '.aos-recovery-20260916/state/host-diagnostic-recovery/install'
STATE = ROOT.parent / '.aos-recovery-20260916/state/bootstrap-action-recovery/install'
BUNDLE_ROOT = ROOT.parent / '.aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete'
PREVIOUS_ID = '1cc13337-c1de-40a7-b45e-acb41f20a19b'
PREVIOUS_GENERATION = 'ba5d7266-5e7e-454f-85c0-04709305592f'
VERSIONS = {'domain.ecommerce.core': '1.4.0', 'platform.ecommerce.niushop': '1.23.0',
            'solution.ecommerce.growth': '1.10.0', 'solution.ecommerce.operations-base': '1.2.0'}
ACTIONS = ('observe', 'disable-h', 'settle-h', 'reconcile-h', 'create-i', 'prepare-i', 'verify-i',
           'stage-i', 'configure-i', 'enable-i')


def initial(label):
    if label not in {'h', 'i'}:
        raise ValueError('only fixed H/I installation labels are allowed')
    path = (OLD_STATE if label == 'h' else STATE) / label / 'create-result.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    identity = result.get('installationId')
    if not isinstance(identity, str) or str(UUID(identity)) != identity:
        raise ValueError('canonical installation identity required')
    if label == 'h' and identity != PREVIOUS_ID:
        raise ValueError('fixed H predecessor differs')
    return result


def load_profile():
    spec = importlib.util.spec_from_file_location('bootstrap_recovery_base_profile', ROOT / 'scripts/a0v_ecommerce_current_reinstall.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE, module.BUNDLE_ROOT, module.VERSIONS = STATE, BUNDLE_ROOT, dict(VERSIONS)
    module._initial = initial
    observe = module.observe_installation
    def checked_observe(identity):
        snapshot = observe(identity)
        if identity == PREVIOUS_ID:
            require_h_identity(snapshot)
        return snapshot
    module.observe_installation = checked_observe
    return module


def require_h_identity(snapshot):
    if str(snapshot['head']['installation_id']) != PREVIOUS_ID:
        raise ValueError('fixed H predecessor required')
    bindings = snapshot.get('bindings', [])
    if len(bindings) != 1 or str(bindings[0]['generation']) != PREVIOUS_GENERATION:
        raise ValueError('fixed H generation required')


def require_retired_h(profile, snapshot):
    require_h_identity(snapshot)
    return profile.replacement_ref(snapshot)


def require_detached_h(connect):
    with connect() as conn:
        rows = conn.execute('''SELECT l.status FROM extension_dispatch_lifecycle_operation l
            JOIN extension_dispatch_cutover_operation c
              ON (c.org_id,c.project_id,c.cutover_operation_id)=(l.org_id,l.project_id,l.activation_operation_id)
            WHERE c.org_id='org-org' AND c.project_id='dev-project'
              AND c.target_installation_id=%s AND c.target_generation=%s AND c.status='resumed' ''',
            (PREVIOUS_ID, PREVIOUS_GENERATION)).fetchall()
        attached = conn.execute('''SELECT count(*) AS n FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s''', (PREVIOUS_ID,)).fetchone()['n']
    if len(rows) != 1 or rows[0]['status'] != 'detached' or attached != 0:
        raise ValueError('exact H disable/detach completion required')


def create_i(profile):
    target = STATE / 'i/create-result.json'
    if target.exists() or (target.parent / 'create-intent.json').exists():
        raise ValueError('I result exists; read receipt instead of resending')
    if initial('h')['installationId'] != PREVIOUS_ID:
        raise ValueError('fixed H predecessor required')
    predecessor = require_retired_h(profile, profile.observe_installation(PREVIOUS_ID))
    from a0v_formal_text_model_renewal import database_connect
    require_detached_h(database_connect('aos_meta_head'))
    helper = profile._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer = profile._load('a0v_canonical_ecommerce_first_install')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=target.parent)
    profile._freeze(target.parent / 'create-intent.json', dict(label='i', predecessor=predecessor,
        versions=VERSIONS, backup=backup))
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect, state_dir=profile.TRUST_STATE,
        core_version=VERSIONS['domain.ecommerce.core'], adapter_version=VERSIONS['platform.ecommerce.niushop'],
        growth_version=VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix='a0v-event-complete-i-20260916', current_installation_ref=predecessor)
    if result['installationState'] != 'approved':
        raise ValueError('I must have its own approved installation')
    profile._freeze(target, result)
    return dict(outcome='DIAGNOSTIC_H_APPROVED', **result)


def require_orphaned_h(connect):
    with connect() as conn:
        rows = conn.execute('''SELECT c.cutover_operation_id,
            (SELECT count(*) FROM extension_operation_dispatch_binding d
             WHERE d.org_id=c.org_id AND d.project_id=c.project_id
               AND d.cutover_group_id=c.cutover_group_id
               AND d.installation_id=c.target_installation_id
               AND d.generation=c.target_generation) AS attached
            FROM extension_dispatch_cutover_operation c
            WHERE c.org_id='org-org' AND c.project_id='dev-project'
              AND c.target_installation_id=%s AND c.target_generation=%s
              AND c.kind='activate' AND c.status='resumed'
              AND NOT EXISTS(SELECT 1 FROM extension_dispatch_lifecycle_operation l
                WHERE l.org_id=c.org_id AND l.project_id=c.project_id
                  AND l.activation_operation_id=c.cutover_operation_id)''',
            (PREVIOUS_ID, PREVIOUS_GENERATION)).fetchall()
    if len(rows) != 1 or rows[0]['attached'] != 9:
        raise ValueError('exact orphaned H dispatch recovery required')
    return str(rows[0]['cutover_operation_id'])


def reconcile_h(profile):
    snapshot = profile.observe_installation(PREVIOUS_ID)
    require_retired_h(profile, snapshot)
    from a0v_formal_text_model_renewal import database_connect
    activation_id = require_orphaned_h(database_connect('aos_meta_head'))
    target = dict(generation=PREVIOUS_GENERATION, bindingRevision=snapshot['bindings'][0]['revision'])
    profile._freeze(STATE / 'h/reconcile-intent.json', dict(installationId=PREVIOUS_ID,
        activationOperationId=activation_id, target=target))
    activation, _store, _lifecycle, service, _dependent = profile._setup_runtime_plane()
    receipt = service.request(**profile.SCOPE, installation_id=PREVIOUS_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key='a0v-eventcomplete-h-reconcile-retirement-20260916', if_match='"5"', target=target)
    return dict(receipt=receipt.response_json, replayed=receipt.replayed)


def run(action, profile):
    if action not in ACTIONS:
        raise ValueError('unsupported fixed event-complete action')
    if action == 'observe':
        result = {'h': profile.observe_installation(PREVIOUS_ID)}
        if (STATE / 'i/create-result.json').exists():
            result['i'] = profile.observe_installation(initial('i')['installationId'])
        return result
    initial('h')
    if action in {'disable-h', 'settle-h'}:
        require_h_identity(profile.observe_installation(PREVIOUS_ID))
    if action == 'disable-h':
        return profile.disable('h', suffix='bootstrap-disable')
    if action == 'settle-h':
        return profile.settle_released('h')
    if action == 'reconcile-h':
        return reconcile_h(profile)
    if action == 'create-i':
        return create_i(profile)
    phase, label = action.split('-')
    if phase in {'prepare', 'verify'}:
        return profile.lifecycle(label, phase)
    return profile.configure(label, phase)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('immutable output exists; inspect before retry')
    profile = load_profile()
    result = run(args.action, profile)
    profile._freeze_or_match(args.output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == '__main__':
    main()
