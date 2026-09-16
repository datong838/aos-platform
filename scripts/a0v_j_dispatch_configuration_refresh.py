"""One approved, no-effect J dispatch refresh with retained idempotent evidence."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/dispatch-configuration-refresh/business/refresh'
SCOPE = {'org_id': 'org-org', 'project_id': 'dev-project'}
CANARY = {'org_id': 'dev-org', 'project_id': 'dev-project'}
INSTALLATION = 'd6531562-e388-4206-a3ba-a89aaddc255c'
GENERATION = '5295b81e-6005-4c2e-befc-3323f1456b8c'
GROUP = '6a402d31-83ad-546c-807f-508c87498ce1'
ACTOR = 'a0v-ecommerce-growth-1.4-runtime-owner'
KEY = 'a0v-qyh-event-complete-j-configuration-refresh-v1'
SOURCE_CONFIG = {'configurationId': 'e2fdde1f-ebdb-4863-b158-7204735f3fe8', 'revision': 1,
                 'hash': 'sha256:91ca4b1b840890be7c664edcac37f4b7ca76bddc29e3549e90dd9c679d32c0c5'}
TARGET_CONFIG = {'configurationId': 'e2fdde1f-ebdb-4863-b158-7204735f3fe8', 'revision': 2,
                 'hash': 'sha256:e60388471f9cba40e8cc80d82c8e1ee8c4775dc9dc09e974f1aca3ada5e10091'}
CONFIGURE = '99d44b1d-e470-4f1b-ae9e-7700d0d24f0d'
ENABLE = 'a81beb7e-6991-4b3d-a1c1-b311a36dce8a'
ACTION_TYPE = {'id': 'ecommerce_dispatch_configuration_refresh', 'name': '电商分发配置接续',
               'objectType': 'BundleInstallation', 'parameters': [], 'requiredMarkings': [],
               'submissionCriteria': []}


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    normalized = json.loads(json.dumps(value, ensure_ascii=False, default=str))
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    normalized = json.loads(json.dumps(value, ensure_ascii=False, default=str))
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != normalized:
            raise ValueError('retained refresh material differs')
        return
    freeze(path, normalized)


def load(name: str) -> dict[str, Any]:
    path = STATE / f'{name}-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f'private {name} result required')
    return json.loads(path.read_text(encoding='utf-8'))


def boot():
    sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'services/aos-api')]
    from a0v_dispatch_configuration_refresh_clone import profile
    deployment = profile()
    deployment.require_lease()
    from a0v_product_controlled_api import load_launcher
    readiness = load_launcher().preflight()
    if readiness.get('outcome') != 'CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN':
        raise ValueError('controlled main database identity preflight required')
    if not os.getenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE'):
        raise ValueError('protected registration identity required')
    return deployment


def reconstruct() -> dict[str, Any]:
    from aos_api.ecommerce_dispatch_configuration_contracts import DispatchConfigurationRefreshRequest
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    deployment = boot()
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        head = conn.execute("""SELECT i.etag_version,r.lock_hash,r.overlay_revision,r.state
            FROM bundle_installation i JOIN bundle_installation_revision r
              ON r.installation_pk=i.installation_pk AND r.revision=i.current_revision
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
            (*SCOPE.values(), INSTALLATION)).fetchone()
        binding = conn.execute("""SELECT revision,execution_epoch,desired_state,observed_state,enabled,
            operation_fence,config_ref FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s""",
            (*SCOPE.values(), INSTALLATION, GENERATION)).fetchone()
        resume = conn.execute("""SELECT o.cutover_operation_id,r.receipt_id,r.content_hash
            FROM extension_dispatch_cutover_operation o JOIN extension_dispatch_cutover_receipt r
              USING(org_id,project_id,cutover_operation_id)
            WHERE o.org_id=%s AND o.project_id=%s AND o.cutover_group_id=%s AND o.kind='activate'
              AND o.status='resumed' AND o.target_installation_id=%s AND o.target_generation=%s
              AND r.phase='resume'""", (*SCOPE.values(), GROUP, INSTALLATION, GENERATION)).fetchall()
        dispatch = [dict(row) for row in conn.execute("""SELECT operation_id,revision,execution_epoch,
            operation_fence,cutover_group_revision,handler_kind,installation_id,generation
            FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s
              AND cutover_group_id=%s AND operation_id=ANY(%s) ORDER BY operation_id""",
              (*SCOPE.values(), GROUP, list(ECOMMERCE_GROWTH_OPERATIONS))).fetchall()]
        event_control = dict(conn.execute("""SELECT operation_id,revision,execution_epoch,
            operation_fence,cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
              AND operation_id='ecommerce_growth_event_control'""", (*SCOPE.values(), GROUP)).fetchone())
        operations = {str(row['operation_id']): dict(row) for row in conn.execute("""SELECT operation_id,
            kind,status,phase,revision,requested_by,installation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND operation_id=ANY(%s::uuid[])""",
            (*SCOPE.values(), [CONFIGURE, ENABLE])).fetchall()}
        refresh_count = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt
            WHERE org_id=%s AND project_id=%s""", tuple(SCOPE.values())).fetchone()['n']
        schedule_count = conn.execute("""SELECT count(*) AS n FROM automation_schedule_binding
            WHERE org_id=%s AND project_id=%s AND enabled""", tuple(SCOPE.values())).fetchone()['n']
    if (head is None or dict(head) != {'etag_version': 5,
            'lock_hash': 'sha256:85f986267d34c4847b7045144a61539a7f57abfc75ac582721b27e6b3cd5d785',
            'overlay_revision': 'a0v-canonical-ecommerce-v1', 'state': 'active'}):
        raise ValueError('current J installation differs')
    if binding is None or dict(binding) != {'revision': 9, 'execution_epoch': 5,
            'desired_state': 'enabled', 'observed_state': 'ready', 'enabled': True,
            'operation_fence': False, 'config_ref': TARGET_CONFIG}:
        raise ValueError('current J target binding differs')
    expected_ids = sorted(ECOMMERCE_GROWTH_OPERATIONS)
    if ([row['operation_id'] for row in dispatch] != expected_ids or len(dispatch) != 9
            or any(row['revision'] != 17 or row['execution_epoch'] != 3
                   or row['operation_fence'] is not False or row['cutover_group_revision'] != 30
                   or row['handler_kind'] != 'extension' or str(row['installation_id']) != INSTALLATION
                   or str(row['generation']) != GENERATION for row in dispatch)):
        raise ValueError('exact pre-refresh dispatch group required')
    if event_control != {'operation_id': 'ecommerce_growth_event_control', 'revision': 1,
            'execution_epoch': 3, 'operation_fence': False, 'cutover_group_revision': 30}:
        raise ValueError('independent event-control dispatch baseline required')
    if len(resume) != 1 or refresh_count != 0 or schedule_count != 0:
        raise ValueError('one original resume and no prior refresh or enabled schedule required')
    if set(operations) != {CONFIGURE, ENABLE}:
        raise ValueError('exact configure and enable operations required')
    for operation_id, kind, revision in ((CONFIGURE, 'configure', 6), (ENABLE, 'enable', 5)):
        row = operations[operation_id]
        if (row['kind'], row['status'], row['phase'], row['revision'], row['requested_by'],
                str(row['installation_id'])) != (kind, 'succeeded', 'succeeded', revision, ACTOR, INSTALLATION):
            raise ValueError(f'exact {kind} operation differs')
    root = resume[0]
    base = {
        'schemaVersion': 'aos.ecommerce.dispatch-configuration-refresh/v1', **SCOPE,
        'installationRef': {'installationId': INSTALLATION, 'revision': 5,
            'lockHash': head['lock_hash'], 'overlayRevision': head['overlay_revision']},
        'generation': GENERATION, 'cutoverGroupId': GROUP, 'expectedGroupRevision': 30,
        'sourceAuthorityRef': {'resourceType': 'CutoverResumeReceipt',
            'resourceId': str(root['receipt_id']), 'revision': 1, 'contentHash': root['content_hash']},
        'sourceRuntimeRevision': 6, 'sourceExecutionEpoch': 3,
        'sourceConfigurationRef': SOURCE_CONFIG, 'targetRuntimeRevision': 9,
        'targetExecutionEpoch': 5, 'targetConfigurationRef': TARGET_CONFIG,
        'configureOperationId': CONFIGURE, 'configureOperationRevision': 6,
        'enableOperationId': ENABLE, 'enableOperationRevision': 5,
        'operationIds': tuple(expected_ids), 'idempotencyKey': KEY,
        'externalEffectsAllowed': False, 'resumeBusinessRuns': False,
    }
    # Validate every field now; a nonzero placeholder is excluded from approval_intent.
    probe = {**base, 'approvalRef': {'resourceType': 'ActionApprovalEvent',
        'resourceId': '00000000-0000-0000-0000-000000000001', 'revision': 1,
        'contentHash': 'sha256:' + '1' * 64}}
    request = DispatchConfigurationRefreshRequest.model_validate(probe)
    return {'outcome': 'J_DISPATCH_CONFIGURATION_REFRESH_RECONSTRUCTED',
            'requestWithoutApproval': request.approval_intent(), 'dispatchBefore': dispatch,
            'eventControlBefore': event_control,
            'refreshRowsBefore': refresh_count, 'enabledSchedules': schedule_count}


def ensure_action_type() -> dict[str, Any]:
    deployment = boot()
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        row = conn.execute("""SELECT id,name,object_type,parameters,required_markings,submission_criteria
            FROM meta_action_type WHERE id=%s""", (ACTION_TYPE['id'],)).fetchone()
    current = None if row is None else {'id': row['id'], 'name': row['name'],
        'objectType': row['object_type'], 'parameters': row['parameters'],
        'requiredMarkings': row['required_markings'], 'submissionCriteria': row['submission_criteria']}
    if current is not None and current != ACTION_TYPE:
        raise ValueError('current refresh ActionType differs')
    freeze_or_match(STATE / 'action-type-intent.json', {'actor': 'user:dev', 'actionType': ACTION_TYPE})
    if current is None:
        from a0v_qyh_current_product_event_first_chain import api
        _status, current = api('POST', '/v1/actions/types', ACTION_TYPE)
    result = {'outcome': 'J_DISPATCH_CONFIGURATION_REFRESH_ACTION_TYPE_READY',
              'actionType': current, 'created': row is None}
    freeze(STATE / 'action-type-result.json', result)
    return result


def approve() -> dict[str, Any]:
    boot()
    material = reconstruct()
    payload = material['requestWithoutApproval']
    freeze_or_match(STATE / 'approval-owner-intent.json', {'maker': ACTOR,
        'checker': 'a0v-ecommerce-growth-1.4-approval-checker', 'payload': payload})
    from a0v_qyh_current_product_event_first_chain import _approve
    bundle, ref = _approve(ACTION_TYPE['id'], payload, KEY + ':authority-owner-v1')
    if bundle.proposal.risk_level.value != 'R2':
        raise ValueError('independent R2 refresh approval required')
    result = {'outcome': 'J_DISPATCH_CONFIGURATION_REFRESH_APPROVED',
              'proposalId': bundle.proposal.id,
              'approvalRef': {key: value for key, value in ref.items() if key != 'receiptId'},
              'requestWithoutApproval': payload}
    freeze(STATE / 'approval-result.json', result)
    return result


def execute() -> dict[str, Any]:
    boot()
    approved = load('approval')
    current = reconstruct()['requestWithoutApproval']
    if current != approved['requestWithoutApproval']:
        raise ValueError('approved refresh target drifted')
    command = {**current, 'approvalRef': approved['approvalRef']}
    freeze_or_match(STATE / 'execute-intent.json', {'actor': ACTOR, 'command': command})
    from aos_api.ecommerce_dispatch_configuration_owner import EcommerceDispatchConfigurationOwner
    from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.tenant_scope import TenantScope
    scope = TenantScope(**SCOPE)
    with scoped_cutover_connection(registration_connection)(scope) as conn:
        receipt = EcommerceDispatchConfigurationOwner().execute(conn, scope=scope, command=command, actor=ACTOR)
        conn.commit()
    result = {'outcome': 'J_DISPATCH_CONFIGURATION_REFRESH_EXECUTED', 'receipt': receipt}
    freeze(STATE / 'execute-result.json', result)
    return result


def inspect(*, replay: bool = False) -> dict[str, Any]:
    deployment = boot()
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    executed = load('execute')
    command = executed['receipt']['request']
    if replay:
        from aos_api.ecommerce_dispatch_configuration_owner import EcommerceDispatchConfigurationOwner
        from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
        from aos_api.ecommerce_growth_registration_connection import registration_connection
        from aos_api.tenant_scope import TenantScope
        scope = TenantScope(**SCOPE)
        with scoped_cutover_connection(registration_connection)(scope) as conn:
            repeated = EcommerceDispatchConfigurationOwner().execute(
                conn, scope=scope, command=command, actor=ACTOR)
            conn.commit()
        if repeated != executed['receipt']:
            raise ValueError('same-key refresh replay returned different receipt')
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        rows = [dict(row) for row in conn.execute("""SELECT operation_id,revision,execution_epoch,
            operation_fence,cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
              AND operation_id=ANY(%s) ORDER BY operation_id""",
            (*SCOPE.values(), GROUP, sorted(ECOMMERCE_GROWTH_OPERATIONS))).fetchall()]
        event_control = dict(conn.execute("""SELECT operation_id,revision,execution_epoch,
            operation_fence,cutover_group_revision FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s
              AND operation_id='ecommerce_growth_event_control'""", (*SCOPE.values(), GROUP)).fetchone())
        receipts = [dict(row) for row in conn.execute("""SELECT receipt_id,revision,request_hash,content_hash,
            idempotency_key FROM extension_dispatch_configuration_refresh_receipt
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s ORDER BY revision""",
            (*SCOPE.values(), GROUP)).fetchall()]
    if (len(rows) != 9 or any(row['revision'] != 18 or row['execution_epoch'] != 5
            or row['operation_fence'] is not False or row['cutover_group_revision'] != 31 for row in rows)
            or len(receipts) != 1 or str(receipts[0]['receipt_id']) != executed['receipt']['ref']['resourceId']
            or receipts[0]['revision'] != 1 or receipts[0]['idempotency_key'] != KEY):
        raise ValueError('atomic refreshed dispatch or receipt readback differs')
    if event_control != {'operation_id': 'ecommerce_growth_event_control', 'revision': 1,
            'execution_epoch': 3, 'operation_fence': False, 'cutover_group_revision': 30}:
        raise ValueError('configuration refresh mutated event-control dispatch')
    from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.tenant_scope import TenantScope
    with scoped_cutover_connection(registration_connection)(TenantScope(**CANARY)) as conn:
        canary = conn.execute('SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt').fetchone()['n']
    if canary != 0:
        raise ValueError('canary tenant observed refresh history')
    result = {'outcome': ('J_DISPATCH_CONFIGURATION_REFRESH_REPLAY_GREEN' if replay
                           else 'J_DISPATCH_CONFIGURATION_REFRESH_READBACK_GREEN'),
              'receipt': receipts[0], 'dispatch': rows, 'eventControl': event_control,
              'canaryVisibleRows': canary,
              'sameKeyReplay': replay, 'externalEffects': 0, 'businessRunsResumed': 0}
    freeze(STATE / ('replay-result.json' if replay else 'inspect-result.json'), result)
    return result


def run(action: str) -> dict[str, Any]:
    if action == 'preflight':
        return reconstruct()
    if action == 'action-type':
        return ensure_action_type()
    if action == 'approve':
        return approve()
    if action == 'execute':
        return execute()
    return inspect(replay=action == 'replay')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('preflight', 'action-type', 'approve', 'execute', 'inspect', 'replay'))
    print(json.dumps(run(parser.parse_args().action), ensure_ascii=False, default=str, indent=2))
