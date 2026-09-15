"""Fixed F/growth-1.9 profile; original A-E commands and receipts are retained."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID

os.environ.setdefault('AOS_DOTENV_DISABLED', '1')
ROOT = Path(__file__).resolve().parents[1]
OLD_STATE = ROOT.parent / '.aos-recovery-20260915/state/current-ecommerce-package/install'
STATE = ROOT.parent / '.aos-recovery-20260916/state/growth-1.9-current-package/install'
BUNDLE_ROOT = ROOT.parent / '.aos-recovery-20260916/state/growth-1.9-current-package/registry/signed-bundles-growth-1.9-current'
E_ID = '1c08edfb-ec0d-4abb-a411-7b6ec0d6066a'
E_GENERATION = 'ebaa620a-8831-4c2a-b971-788383f352f8'
VERSIONS = {'domain.ecommerce.core': '1.3.0', 'platform.ecommerce.niushop': '1.23.0',
            'solution.ecommerce.growth': '1.9.0', 'solution.ecommerce.operations-base': '1.2.0'}
ACTIONS = ('observe', 'disable-e', 'settle-e', 'create-f', 'prepare-f', 'verify-f',
           'stage-f', 'configure-f', 'enable-f')


def initial(label):
    if label not in {'e', 'f'}:
        raise ValueError('only fixed E/F installation labels are allowed')
    path = (OLD_STATE if label == 'e' else STATE) / label / 'create-result.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    identity = result.get('installationId')
    if not isinstance(identity, str) or str(UUID(identity)) != identity:
        raise ValueError('canonical installation identity required')
    if label == 'e' and identity != E_ID:
        raise ValueError('fixed E predecessor differs')
    return result


def load_profile():
    spec = importlib.util.spec_from_file_location('growth19_base_profile', ROOT / 'scripts/a0v_ecommerce_current_reinstall.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.STATE, module.BUNDLE_ROOT, module.VERSIONS = STATE, BUNDLE_ROOT, dict(VERSIONS)
    module._initial = initial
    observe = module.observe_installation
    def checked_observe(identity):
        snapshot = observe(identity)
        if identity == E_ID:
            require_e_identity(snapshot)
        return snapshot
    module.observe_installation = checked_observe
    return module


def require_e_identity(snapshot):
    if str(snapshot['head']['installation_id']) != E_ID:
        raise ValueError('fixed E predecessor required')
    bindings = snapshot.get('bindings', [])
    if len(bindings) != 1 or str(bindings[0]['generation']) != E_GENERATION:
        raise ValueError('fixed E generation required')


def require_retired_e(profile, snapshot):
    require_e_identity(snapshot)
    return profile.replacement_ref(snapshot)


def require_detached_e(connect):
    with connect() as conn:
        rows = conn.execute('''SELECT l.status FROM extension_dispatch_lifecycle_operation l
            JOIN extension_dispatch_cutover_operation c
              ON (c.org_id,c.project_id,c.cutover_operation_id)=(l.org_id,l.project_id,l.activation_operation_id)
            WHERE c.org_id='org-org' AND c.project_id='dev-project'
              AND c.target_installation_id=%s AND c.target_generation=%s AND c.status='resumed' ''',
            (E_ID, E_GENERATION)).fetchall()
        attached = conn.execute('''SELECT count(*) AS n FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s''', (E_ID,)).fetchone()['n']
    if len(rows) != 1 or rows[0]['status'] != 'detached' or attached != 0:
        raise ValueError('exact E disable/detach completion required')


def create_f(profile):
    target = STATE / 'f/create-result.json'
    if target.exists():
        raise ValueError('F result exists; read receipt instead of resending')
    if initial('e')['installationId'] != E_ID:
        raise ValueError('fixed E predecessor required')
    predecessor = require_retired_e(profile, profile.observe_installation(E_ID))
    from a0v_formal_text_model_renewal import database_connect
    require_detached_e(database_connect('aos_meta_head'))
    helper = profile._load('a0v_ecommerce_growth_1_5_registry_successor')
    installer = profile._load('a0v_canonical_ecommerce_first_install')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=target.parent)
    profile._freeze(target.parent / 'create-intent.json', dict(label='f', predecessor=predecessor,
        versions=VERSIONS, backup=backup))
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect, state_dir=profile.TRUST_STATE,
        core_version=VERSIONS['domain.ecommerce.core'], adapter_version=VERSIONS['platform.ecommerce.niushop'],
        growth_version=VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix='a0v-growth-1.9-f-20260916', current_installation_ref=predecessor)
    if result['installationState'] != 'approved':
        raise ValueError('F must have its own approved installation')
    profile._freeze(target, result)
    return dict(outcome='GROWTH_1_9_F_APPROVED', **result)


def run(action, profile):
    if action not in ACTIONS:
        raise ValueError('unsupported fixed growth 1.9 action')
    if action == 'observe':
        result = {'e': profile.observe_installation(E_ID)}
        if (STATE / 'f/create-result.json').exists():
            result['f'] = profile.observe_installation(initial('f')['installationId'])
        return result
    initial('e')
    if action in {'disable-e', 'settle-e'}:
        require_e_identity(profile.observe_installation(E_ID))
    if action == 'disable-e':
        return profile.disable('e', suffix='growth19-disable')
    if action == 'settle-e':
        return profile.settle_released('e')
    if action == 'create-f':
        return create_f(profile)
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
    profile._freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == '__main__':
    main()
