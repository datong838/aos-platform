"""Fixed J configuration successor before the no-effect dispatch refresh."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/dispatch-configuration-refresh/business/configuration'
INSTALLATION = 'd6531562-e388-4206-a3ba-a89aaddc255c'
GENERATION = '5295b81e-6005-4c2e-befc-3323f1456b8c'
SOURCE_CONFIG = {
    'configurationId': 'e2fdde1f-ebdb-4863-b158-7204735f3fe8',
    'revision': 1,
    'hash': 'sha256:91ca4b1b840890be7c664edcac37f4b7ca76bddc29e3549e90dd9c679d32c0c5',
}
BUNDLE_ROOT = ROOT.parent / '.aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete'
TASK = 'SC4-5L6Y5F4-REFRESH-DEPLOY-20260916'


def freeze(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict) -> None:
    normalized = json.loads(json.dumps(value, ensure_ascii=False, default=str))
    if path.exists():
        if json.loads(path.read_text()) != normalized:
            raise ValueError('retained configuration successor intent differs')
        return
    freeze(path, normalized)


def load_profile():
    path = ROOT / 'scripts/a0v_ecommerce_1_7_configure.py'
    spec = importlib.util.spec_from_file_location('j_configuration_successor_base', path)
    profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(profile)
    profile.BUNDLE_ROOT = BUNDLE_ROOT

    def target(recovery=False, *, sleep_recovery=False, niushop_1_4=False):
        if any((recovery, sleep_recovery, niushop_1_4)):
            raise ValueError('only exact current J configuration successor allowed')
        return (
            INSTALLATION,
            STATE / 'configuration-successor.json',
            'a0v-current-ecommerce-j-refresh-20260916',
            'current-ecommerce-j-refresh-20260916',
        )

    profile.configuration_target = target
    return profile


def preflight(action: str) -> dict:
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    from a0v_dispatch_configuration_refresh_clone import profile as deployment_profile

    deployment = deployment_profile()
    deployment.require_lease()
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if deployment.storage.version(conn) != ['a0v_068']:
            raise ValueError('deployed a0v068 required')
        binding = conn.execute("""SELECT generation,revision,execution_epoch,desired_state,observed_state,
            enabled,operation_fence,config_ref FROM extension_runtime_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""", (INSTALLATION,)).fetchone()
        if binding is None or str(binding['generation']) != GENERATION:
            raise ValueError('exact current J generation required')
        rows = conn.execute("""SELECT operation_id,handler_kind,installation_id,generation,execution_epoch,
            operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project'
              AND operation_id LIKE 'ecommerce_growth_%' ORDER BY operation_id""").fetchall()
        refreshes = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt
            WHERE org_id='org-org' AND project_id='dev-project'""").fetchone()['n']
        canary = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt
            WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()['n']
        schedules = conn.execute("""SELECT count(*) AS n FROM automation_schedule_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND enabled""").fetchone()['n']
    state = dict(binding)
    if action in {'preflight', 'stage-successor'}:
        expected = dict(revision=6, execution_epoch=3, desired_state='enabled', observed_state='ready', enabled=True, operation_fence=False)
        if any(state[key] != value for key, value in expected.items()) or state['config_ref'] != SOURCE_CONFIG:
            raise ValueError('exact pre-successor J binding required')
        if refreshes != 0:
            raise ValueError('refresh must not exist before configuration successor')
    elif action == 'configure':
        if state['revision'] != 6 or state['execution_epoch'] != 3 or state['config_ref'] != SOURCE_CONFIG:
            raise ValueError('configuration stage must not mutate binding')
    elif action == 'enable':
        if (
            state['revision'] != 8
            or state['execution_epoch'] != 4
            or state['enabled'] is not False
            or state['operation_fence'] is not True
            or state['desired_state'] != 'disabled'
            or state['observed_state'] != 'unknown'
            or not state['config_ref']
            or state['config_ref']['configurationId'] != SOURCE_CONFIG['configurationId']
            or state['config_ref']['revision'] != 2
        ):
            raise ValueError('exact configured J successor required')
    else:
        raise ValueError('unsupported configuration successor action')
    business = [dict(row) for row in rows if row['operation_id'] != 'ecommerce_growth_event_control']
    if (
        len(business) != 9
        or any(row['handler_kind'] != 'extension' or str(row['installation_id']) != INSTALLATION
               or str(row['generation']) != GENERATION or row['execution_epoch'] != 3
               or row['operation_fence'] is not False or row['cutover_group_revision'] != 30 for row in business)
        or schedules != 0
        or canary != 0
    ):
        raise ValueError('paused exact J dispatch and canary baseline required')
    return dict(
        databaseVersion='a0v_068',
        action=action,
        binding=state,
        businessDispatchCount=len(business),
        refreshRows=refreshes,
        enabledSchedules=schedules,
        canaryRefreshRows=canary,
    )


def stage_successor() -> dict:
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.tenant_scope import TenantScope

    profile = load_profile()
    preview = profile.run('preflight')
    document = ConfigurationDocument.model_validate_json(json.dumps(preview['configuration']))
    connect, activation, authorize, _service = profile.setup()
    scope = TenantScope('org-org', 'dev-project')
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn, org_id=scope.org_id, project_id=scope.project_id)
            staged = append_configuration(
                conn,
                org_id=scope.org_id,
                project_id=scope.project_id,
                installation_id=INSTALLATION,
                generation=GENERATION,
                expected_installation_etag=5,
                expected_binding_revision=6,
                actor=activation.ACTOR,
                idempotency_key='a0v-current-ecommerce-j-refresh-20260916-config-successor-stage-v1',
                configuration=document,
                authorize=authorize,
                previous_ref=SOURCE_CONFIG,
            )
    if staged.configurationId != SOURCE_CONFIG['configurationId'] or staged.revision != 2:
        raise ValueError('same-family configuration successor required')
    frozen = dict(
        installationEtag=5,
        bindingRevision=6,
        generation=GENERATION,
        configuration=document.model_dump(mode='json'),
        configRef=staged.model_dump(mode='json'),
    )
    freeze(STATE / 'configuration-successor.json', frozen)
    return dict(action='stage-successor', installationId=INSTALLATION, staged=frozen, authorized=True)


def run(action: str) -> dict:
    snapshot = preflight(action)
    if action == 'preflight':
        return dict(outcome='J_CONFIGURATION_SUCCESSOR_PREFLIGHT_GREEN', **snapshot)
    intent = STATE / f'{action}-intent.json'
    result_path = STATE / f'{action}-result.json'
    if result_path.exists():
        raise ValueError('configuration successor result already exists; inspect instead of resending')
    freeze_or_match(intent, dict(installationId=INSTALLATION, generation=GENERATION, action=action, preflight=snapshot))
    result = stage_successor() if action == 'stage-successor' else load_profile().run(action)
    payload = dict(outcome=f'J_CONFIGURATION_SUCCESSOR_{action.upper()}_ACCEPTED', result=result)
    freeze(result_path, payload)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('preflight', 'stage-successor', 'configure', 'enable'))
    print(json.dumps(run(parser.parse_args().action), ensure_ascii=False, default=str, indent=2))
