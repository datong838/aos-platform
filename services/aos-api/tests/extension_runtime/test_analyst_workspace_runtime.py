import importlib
from copy import deepcopy
from io import BytesIO
import json
import struct

import pytest

from test_analyst_workspace_view import projector, snapshot


class NoBusinessPorts:
    def __getattr__(self, name):
        pytest.fail(f'pure projection attempted context access: {name}')


def _frame(kind, method, payload, sequence):
    raw = json.dumps(dict(schemaVersion=1, type=kind, method=method, requestId=f'read-{sequence}',
        parentRequestId=None, payload=payload, sequence=sequence)).encode()
    return struct.pack('>I', len(raw)) + raw


def _responses(target):
    target.seek(0)
    result = []
    while header := target.read(4):
        result.append(json.loads(target.read(struct.unpack('>I', header)[0])))
    return result


def test_persistent_sdk_register_then_invoke_read_method(projector):
    package = importlib.import_module('ecommerce_growth')
    serve = importlib.import_module('aos_extension_sdk.session').serve_session
    source = snapshot()
    original = deepcopy(source)
    wire = BytesIO(_frame('register', 'register', {}, 0) +
                   _frame('invoke', 'analyst_workspace_view_v1', {'snapshot': source}, 1))
    target = BytesIO()
    serve(package.register, package.handle, source=wire, target=target)
    registration, response = _responses(target)
    apis = registration['payload']['contributions']
    assert len(apis) == 10 and len({claim['operationId'] for claim in apis}) == 10
    assert next(c for c in apis if c['operationId'] == 'analyst_workspace_view_v1') == dict(
        kind='api', operationId='analyst_workspace_view_v1', method='POST',
        path='/ecommerce/growth/workspace/view', mode='exclusive')
    assert response['requestId'] == 'read-1' and response['sequence'] == 1
    assert response['payload'] == projector(source)
    assert response['payload']['executionAllowed'] is False
    assert source == original


def test_read_does_not_use_business_ports(projector):
    package = importlib.import_module('ecommerce_growth')
    assert package.handle('analyst_workspace_view_v1', {'snapshot': snapshot()}, NoBusinessPorts()) == projector(snapshot())


@pytest.mark.parametrize('payload', [None, {}, {'snapshot': {}, 'approved': True}, {'query': {}}, {'snapshot': {}}])
def test_invalid_read_payload_rejected(projector, payload):
    package = importlib.import_module('ecommerce_growth')
    with pytest.raises(ValueError):
        package.handle('analyst_workspace_view_v1', payload, NoBusinessPorts())


def test_existing_business_methods_remain_closed_for_unqualified_payload(projector):
    package = importlib.import_module('ecommerce_growth')
    old = [claim for claim in package.register(NoBusinessPorts())['contributions']
           if claim['operationId'] != 'analyst_workspace_view_v1']
    assert len(old) == 9
    for claim in old:
        with pytest.raises(PermissionError):
            package.handle(claim['operationId'], {}, NoBusinessPorts())


def test_forged_snapshot_rejected_through_sdk(projector):
    package = importlib.import_module('ecommerce_growth')
    serve = importlib.import_module('aos_extension_sdk.session').serve_session
    forged = snapshot()
    forged['cases'][0]['case']['title'] = 'forged title'
    wire = BytesIO(_frame('register', 'register', {}, 0) +
                   _frame('invoke', 'analyst_workspace_view_v1', {'snapshot': forged}, 1))
    target = BytesIO()
    with pytest.raises(ValueError, match='hash differs'):
        serve(package.register, package.handle, source=wire, target=target)
    assert len(_responses(target)) == 1
