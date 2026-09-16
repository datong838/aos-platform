"""Fixed J uninstall and K replacement recovery through existing Owners."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import UUID

import a0v_ecommerce_transaction_reinstall as transaction


ROOT = transaction.ROOT
STATE = transaction.STATE / 'recovery-k'
K_DIR = STATE / 'k'
L_DIR = STATE / 'l'
J_ID = 'd6531562-e388-4206-a3ba-a89aaddc255c'
J_GENERATION = '5295b81e-6005-4c2e-befc-3323f1456b8c'
J_LOCK = 'sha256:85f986267d34c4847b7045144a61539a7f57abfc75ac582721b27e6b3cd5d785'
J_DETACH = '15f04808-68e3-481f-9e20-9c6cf43a49a8'
J_DETACH_HASH = 'sha256:da0fbd2e59fc3176274eade80acbdd58f2bce8fdbf24b29843b334c76c0c0f98'
GROUP = '6a402d31-83ad-546c-807f-508c87498ce1'
PREFIX = 'a0v-event-complete-k-reinstall-20260916'
ACTIONS = ('preflight', 'create-k', 'uninstall-j', 'prepare-k', 'verify-k',
           'reset-k', 'create-l', 'uninstall-k', 'prepare-l', 'verify-l',
           'stage-l', 'configure-l', 'enable-l', 'observe')


def profile():
    current = transaction.load_profile()
    current.STATE = STATE

    def initial(label):
        if label == 'j':
            return transaction.initial('j')
        if label not in {'k', 'l'}:
            raise ValueError('only fixed J/K/L labels are allowed')
        value = json.loads(({'k': K_DIR, 'l': L_DIR}[label] / 'create-result.json').read_text())
        identity = value.get('installationId')
        if not isinstance(identity, str) or str(UUID(identity)) != identity:
            raise ValueError('canonical K installation required')
        return value

    current._initial = initial
    return current


def _database_snapshot(current):
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect('aos_meta_head')() as conn:
        receipt = conn.execute('''SELECT receipt_id,phase,authority_data,content_hash
            FROM extension_dispatch_lifecycle_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND receipt_id=%s''',
            (J_DETACH,)).fetchone()
        rows = conn.execute('''SELECT operation_id,handler_kind,installation_id,generation,
            execution_epoch,operation_fence,revision,cutover_group_revision
            FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY operation_id''', (GROUP,)).fetchall()
        inflight = dict(conn.execute('''SELECT
            (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s AND generation=%s
              AND state='running') AS running,
            (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
              USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org'
              AND a.project_id='dev-project' AND o.installation_id=%s AND o.generation=%s
              AND a.status IN ('claimed','unknown')) AS unresolved''',
            (J_ID, J_GENERATION, J_ID, J_GENERATION)).fetchone())
        versions = [dict(row) for row in conn.execute('SELECT version_num FROM alembic_version').fetchall()]
    if (receipt is None or str(receipt['receipt_id']) != J_DETACH or receipt['phase'] != 'detach'
        or receipt['content_hash'] != J_DETACH_HASH
        or canonical_sha256(receipt['authority_data']) != J_DETACH_HASH):
        raise ValueError('exact J detach Receipt required')
    if (len(rows) != len(ECOMMERCE_GROWTH_OPERATIONS)
        or [row['operation_id'] for row in rows] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
        or any(row['handler_kind'] != 'legacy' or row['installation_id'] is not None
               or row['generation'] is not None or row['execution_epoch'] is not None
               or row['operation_fence'] is not True or row['revision'] != 20
               or row['cutover_group_revision'] != 35 for row in rows)):
        raise ValueError('exact detached J business routes required')
    return dict(version=versions, detachReceiptId=J_DETACH,
                detachContentHash=J_DETACH_HASH, routes=len(rows),
                routeRevision=20, groupRevision=35, inflight=inflight)


def require_j(current):
    snapshot = current.observe_installation(J_ID)
    head, bindings = snapshot['head'], snapshot['bindings']
    if (str(head['installation_id']) != J_ID or head['etag_version'] != 5
        or head['state'] != 'active' or head['lock_hash'] != J_LOCK
        or head['overlay_revision'] != 'a0v-canonical-ecommerce-v1'
        or len(bindings) != 1 or str(bindings[0]['generation']) != J_GENERATION
        or bindings[0]['revision'] != 11 or bindings[0]['execution_epoch'] != 6
        or bindings[0]['enabled'] is not False or bindings[0]['operation_fence'] is not True
        or bindings[0]['desired_state'] != 'disabled'
        or bindings[0]['observed_state'] != 'unknown'
        or len(snapshot['resources']) != 3
        or any(row['cleanup_state'] != 'released' or row['observed_release'] is not True
               for row in snapshot['resources'])
        or any(row['status'] not in {'succeeded', 'failed', 'cancelled'}
               for row in snapshot['operations'])
        or snapshot['canaryInstallations'] != 0):
        raise ValueError('exact disabled released J installation required')
    return snapshot


def preflight(current):
    j = require_j(current)
    database = _database_snapshot(current)
    if database['version'] != [{'version_num': 'a0v_072'}] or database['inflight'] != {
        'running': 0, 'unresolved': 0}:
        raise ValueError('exact a0v072 drained J database required')
    return dict(outcome='J_UNINSTALL_K_REINSTALL_PREFLIGHT_GREEN',
                installationId=J_ID, generation=J_GENERATION,
                bindingRevision=j['bindings'][0]['revision'], database=database,
                canaryInstallations=0, externalEffects=0, businessRunsResumed=0)


def create_k(current):
    before = preflight(current)
    if (K_DIR / 'create-result.json').exists():
        raise ValueError('K result exists; observe without resending')
    predecessor = current.replacement_ref(require_j(current))
    first = current._load('a0v_canonical_ecommerce_first_install')
    helper = current._load('a0v_ecommerce_growth_1_5_registry_successor')
    K_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=K_DIR)
    current._freeze(K_DIR / 'create-intent.json', dict(
        label='k', predecessor=predecessor, versions=transaction.VERSIONS,
        backup=backup, preflight=before))
    connect = first.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = first.create_approved_first_installation(connect_factory=connect,
        state_dir=current.TRUST_STATE,
        core_version=transaction.VERSIONS['domain.ecommerce.core'],
        adapter_version=transaction.VERSIONS['platform.ecommerce.niushop'],
        growth_version=transaction.VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result['installationState'] != 'approved':
        raise ValueError('K approved installation required')
    current._freeze(K_DIR / 'create-result.json', result)
    return dict(outcome='K_REPLACEMENT_INSTALLATION_APPROVED', **result)


def uninstall_j(current):
    require_j(current)
    k = current.observe_installation(current._initial('k')['installationId'])
    if (k['head']['state'], k['head']['etag_version'], k['bindings']) != ('approved', 3, []):
        raise ValueError('approved unprepared K required before J uninstall')
    current._freeze_or_match(STATE / 'j-uninstall-intent.json', dict(
        installationId=J_ID, etag=5, generation=J_GENERATION,
        bindingRevision=11, successorInstallationId=str(k['head']['installation_id']),
        detachReceiptId=J_DETACH, detachContentHash=J_DETACH_HASH))
    legacy = current._load('a0v_ecommerce_invalid_baseline_uninstall')
    store, service = legacy._build(current._installation_connection,
        current.TRUST_STATE / 'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt = service.uninstall(**current.SCOPE, installation_id=J_ID,
        request=UninstallInstallationRequest(
            reason='J disabled and detached; recover through approved K replacement'),
        actor='a0v-ecommerce-growth-1.4-runtime-owner', roles=['admin'], markings=[],
        idempotency_key=PREFIX + '-uninstall-j', if_match='"5"')
    record = store.get_installation(**current.SCOPE, installation_id=J_ID)
    if record.state != 'uninstalled' or record.active_revision is not None:
        raise ValueError('J uninstall readback differs')
    return dict(outcome='J_INSTALLATION_UNINSTALLED_FOR_K_RECOVERY',
                receipt=receipt.response_json, replayed=receipt.replayed,
                state=record.state, successorInstallationId=str(k['head']['installation_id']))


def require_interrupted_k(current, *, reset=False):
    snapshot = current.observe_installation(current._initial('k')['installationId'])
    head = snapshot['head']
    operations = snapshot['operations']
    expected_state, expected_etag = ('applied', 4) if reset else ('approved', 5)
    if (head['state'] != expected_state or head['etag_version'] != expected_etag
        or head['lock_hash'] != current._initial('k')['lockHash']
        or snapshot['bindings'] != [] or len(snapshot['resources']) != 3
        or any(row['cleanup_state'] != 'released' or row['observed_release'] is not True
               for row in snapshot['resources'])
        or len(operations) != 2
        or {row['kind'] for row in operations} != {'runtime-apply', 'runtime-verify'}
        or (reset and not any(row['kind'] == 'runtime-verify'
                             and row['status'] == 'accepted'
                             and row['phase'] == 'accepted'
                             and row['deadline_expired'] is True for row in operations))
        or (not reset and any(row['status'] not in {'succeeded', 'failed', 'cancelled'}
                              for row in operations))
        or snapshot['canaryInstallations'] != 0):
        raise ValueError('exact resettable or terminal released K interruption required')
    return snapshot


def reset_k(current):
    k = require_interrupted_k(current, reset=True)
    k_id = str(k['head']['installation_id'])
    current._freeze_or_match(STATE / 'k-reset-intent.json', dict(
        installationId=k_id, etag=4,
        verifyOperationId=str(next(row['operation_id'] for row in k['operations']
                                   if row['kind'] == 'runtime-verify'))))
    activation, _store, lifecycle, _disable, _dependent = current._setup_runtime_plane()
    receipt = lifecycle.reset_preparation(**current.SCOPE, installation_id=k_id,
        actor=activation.ACTOR, roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=PREFIX + '-reset-k', if_match='"4"')
    after = current.observe_installation(k_id)
    require_interrupted_k(current)
    return dict(outcome='K_INTERRUPTED_PREPARATION_RESET', receipt=receipt.response_json,
                replayed=receipt.replayed, state=after['head']['state'],
                revision=after['head']['etag_version'])


def create_l(current):
    k = require_interrupted_k(current)
    j = current.observe_installation(J_ID)
    database = _database_snapshot(current)
    if (j['head']['state'] != 'uninstalled' or database['inflight'] != {
            'running': 0, 'unresolved': 0}):
        raise ValueError('uninstalled J and drained routes required for L')
    if (L_DIR / 'create-result.json').exists():
        raise ValueError('L result exists; observe without resending')
    first = current._load('a0v_canonical_ecommerce_first_install')
    helper = current._load('a0v_ecommerce_growth_1_5_registry_successor')
    L_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=L_DIR)
    current._freeze(L_DIR / 'create-intent.json', dict(
        label='l', predecessor=None, interruptedInstallationId=str(k['head']['installation_id']),
        versions=transaction.VERSIONS, backup=backup, database=database))
    connect = first.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = first.create_approved_first_installation(connect_factory=connect,
        state_dir=current.TRUST_STATE,
        core_version=transaction.VERSIONS['domain.ecommerce.core'],
        adapter_version=transaction.VERSIONS['platform.ecommerce.niushop'],
        growth_version=transaction.VERSIONS['solution.ecommerce.growth'],
        idempotency_prefix=PREFIX + '-clean-l')
    if result['installationState'] != 'approved':
        raise ValueError('L approved clean installation required')
    current._freeze(L_DIR / 'create-result.json', result)
    return dict(outcome='L_CLEAN_INSTALLATION_APPROVED_AFTER_K_INTERRUPTION', **result)


def uninstall_k(current):
    k = require_interrupted_k(current)
    l = current.observe_installation(current._initial('l')['installationId'])
    if (l['head']['state'], l['head']['etag_version'], l['bindings']) != ('approved', 3, []):
        raise ValueError('approved unprepared L required before K uninstall')
    k_id = str(k['head']['installation_id'])
    current._freeze_or_match(STATE / 'k-uninstall-intent.json', dict(
        installationId=k_id, etag=5,
        successorInstallationId=str(l['head']['installation_id'])))
    legacy = current._load('a0v_ecommerce_invalid_baseline_uninstall')
    store, service = legacy._build(current._installation_connection,
        current.TRUST_STATE / 'signing/trust-roots.json')
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    receipt = service.uninstall(**current.SCOPE, installation_id=k_id,
        request=UninstallInstallationRequest(
            reason='K preparation interrupted and resources released; recover through clean L'),
        actor='a0v-ecommerce-growth-1.4-runtime-owner', roles=['admin'], markings=[],
        idempotency_key=PREFIX + '-uninstall-k', if_match='"5"')
    record = store.get_installation(**current.SCOPE, installation_id=k_id)
    if record.state != 'uninstalled' or record.active_revision is not None:
        raise ValueError('K uninstall readback differs')
    return dict(outcome='K_INTERRUPTED_INSTALLATION_UNINSTALLED',
                receipt=receipt.response_json, replayed=receipt.replayed,
                state=record.state, successorInstallationId=str(l['head']['installation_id']))


def run(action):
    if action not in ACTIONS:
        raise ValueError('unsupported J/K recovery action')
    current = profile()
    if action == 'preflight':
        return preflight(current)
    if action == 'create-k':
        return create_k(current)
    if action == 'uninstall-j':
        return uninstall_j(current)
    if action == 'reset-k':
        return reset_k(current)
    if action == 'create-l':
        return create_l(current)
    if action == 'uninstall-k':
        return uninstall_k(current)
    if action == 'observe':
        result = {'j': current.observe_installation(J_ID)}
        if (K_DIR / 'create-result.json').exists():
            result['k'] = current.observe_installation(current._initial('k')['installationId'])
        if (L_DIR / 'create-result.json').exists():
            result['l'] = current.observe_installation(current._initial('l')['installationId'])
        return result
    phase, label = action.split('-')
    if label not in {'k', 'l'}:
        raise ValueError('only K/L lifecycle may continue')
    predecessor = J_ID if label == 'k' else current._initial('k')['installationId']
    predecessor_name = {'k': 'J', 'l': 'K'}[label]
    if current.observe_installation(predecessor)['head']['state'] != 'uninstalled':
        raise ValueError(f'{predecessor_name} must be formally uninstalled before {label.upper()} lifecycle')
    if phase in {'prepare', 'verify'}:
        return current.lifecycle(label, phase)
    return current.configure(label, phase)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=ACTIONS)
    args = parser.parse_args()
    result_path = STATE / f'{args.action}-result.json'
    if result_path.exists():
        raise ValueError('immutable action result exists; inspect without resending')
    result = run(args.action)
    transaction.load_profile()._freeze(result_path, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == '__main__':
    main()
