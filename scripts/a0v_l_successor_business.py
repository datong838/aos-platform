"""Fixed L successor registration after J/K uninstall recovery."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/original-transaction-recovery/install/recovery-k/business/successor-l/registration'
L_ID = '19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3'
L_GENERATION = '64742c68-5e71-485b-a3c8-edc20be3d101'
LOCK = 'sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8'
CONFIG = {'configurationId': 'e02eeab5-eabf-41b5-82ee-47229b938e2f', 'revision': 1,
          'hash': 'sha256:f98af03c9790f56b50a08d8d876a0b019390225d51577e8fdf0926f775bd1ff4'}
DETACH = '15f04808-68e3-481f-9e20-9c6cf43a49a8'
DETACH_HASH = 'sha256:da0fbd2e59fc3176274eade80acbdd58f2bce8fdbf24b29843b334c76c0c0f98'
GROUP = '6a402d31-83ad-546c-807f-508c87498ce1'
KEY = 'a0v-qyh-reinstall-generation-l-successor'
ACTOR = 'a0v-ecommerce-growth-1.4-runtime-owner'


def request_from(snapshot, parent):
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.asset_registry.canonical_json import canonical_sha256
    head, bindings = snapshot['head'], snapshot['bindings']
    if (str(head['installation_id']) != L_ID or head['etag_version'] != 5
        or head['state'] != 'active' or head['lock_hash'] != LOCK
        or head['overlay_revision'] != 'a0v-canonical-ecommerce-v1'
        or len(bindings) != 1 or snapshot['canaryInstallations'] != 0
        or len(snapshot['resources']) != 3
        or any(row['cleanup_state'] != 'pending' or row['observed_release'] is not False
               for row in snapshot['resources'])
        or len(snapshot['operations']) != 4
        or {row['kind'] for row in snapshot['operations']} != {
            'runtime-apply', 'runtime-verify', 'configure', 'enable'}
        or any(row['status'] != 'succeeded' for row in snapshot['operations'])):
        raise ValueError('exact live L installation required')
    binding = bindings[0]
    if (str(binding['generation']) != L_GENERATION or binding['revision'] != 4
        or binding['execution_epoch'] != 3 or binding['enabled'] is not True
        or binding['operation_fence'] is not False or binding['desired_state'] != 'enabled'
        or binding['observed_state'] != 'ready' or binding['config_ref'] != CONFIG):
        raise ValueError('exact ready L binding required')
    if (str(parent['receipt_id']) != DETACH or parent['phase'] != 'detach'
        or parent['org_id'] != 'org-org' or parent['project_id'] != 'dev-project'
        or parent['content_hash'] != DETACH_HASH
        or canonical_sha256(parent['authority_data']) != DETACH_HASH):
        raise ValueError('exact final J detach required')
    return SuccessorDispatchRegistrationRequest.model_validate({
        'schemaVersion': 'aos.ecommerce.successor-dispatch-registration/v1',
        'expectedGroupRevision': 35,
        'predecessorDetachReceiptRef': {
            'resourceType': 'DispatchDisableDetachReceipt', 'resourceId': DETACH,
            'revision': 1, 'contentHash': DETACH_HASH},
        'registration': {
            'schemaVersion': 'aos.ecommerce.first-dispatch-registration/v1',
            'installationRef': {'installationId': L_ID, 'revision': 5,
                'lockHash': LOCK, 'overlayRevision': head['overlay_revision']},
            'generation': L_GENERATION, 'bindingRevision': 4, 'executionEpoch': 3,
            'configRef': CONFIG, 'groupId': GROUP, 'idempotencyKey': KEY}})


def setup():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    from a0v_event_complete_product_api import load_launcher
    if load_launcher().preflight()['outcome'] != 'CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN':
        raise ValueError('controlled identity preflight required')
    import os
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED'] = '0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def current_request():
    import a0v_j_uninstall_reinstall_recovery as recovery
    from a0v_formal_text_model_renewal import database_connect
    current = recovery.profile()
    snapshot = current.observe_installation(L_ID)
    database = recovery._database_snapshot(current)
    if database['version'] != [{'version_num': 'a0v_073'}] \
            or database['routes'] != 9 or database['routeRevision'] != 20 \
            or database['groupRevision'] != 35 \
            or database['inflight'] != {'running': 0, 'unresolved': 0}:
        raise ValueError('exact legacy fenced group 35 snapshot required')
    with database_connect('aos_meta_head')() as conn:
        parent = conn.execute('''SELECT org_id,project_id,receipt_id,phase,authority_data,content_hash
            FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
            AND receipt_id=%s''', (DETACH,)).fetchone()
    if parent is None:
        raise ValueError('final J detach missing')
    return request_from(snapshot, dict(parent))


def register(plane, request, *, recover=False):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match
    service = plane.first_dispatch_registration_service
    scope = TenantScope('org-org', 'dev-project')
    intent = STATE / 'register-intent.json'
    material = request.model_dump(mode='json', by_alias=True)
    existed = intent.exists()
    freeze_or_match(intent, material)
    if existed:
        try:
            receipt = service.read_successor_receipt(scope=scope, installation_id=L_ID,
                idempotency_key=KEY, actor=ACTOR)
        except LookupError:
            receipt = None
        if receipt is None:
            if recover is not True:
                raise ValueError('exact L registered request readback required')
            receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
            replayed = receipt['replayed']
        else:
            replayed = True
    else:
        if recover is True:
            raise ValueError('recover-register requires retained failed intent')
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
        replayed = receipt['replayed']
    if not receipt or receipt['requestHash'] != request.request_hash():
        raise ValueError('exact L registered request readback required')
    result = {'outcome': 'CURRENT_L_SUCCESSOR_REGISTERED', 'request': material,
              'receipt': receipt, 'replayed': replayed}
    path = STATE / 'register-result.json'
    if not path.exists():
        freeze(path, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preview', 'register', 'recover-register'])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({'outcome': 'CURRENT_L_SUCCESSOR_REQUEST_PREVIEW',
               'request': request.model_dump(mode='json', by_alias=True),
               'requestHash': request.request_hash()}
              if args.mode == 'preview' else register(
                  plane, request, recover=args.mode == 'recover-register'))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
