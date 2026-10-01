"""Transport-only proof; socketpair does not establish formal cross-UID authority."""
import json
import os
import socket
import struct
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from aos_api.aip_budget_consumer_client import (
    BudgetConsumerClientBlocked, BudgetConsumerEndpoint, decode_consumer_response,
    exchange_consumer, request_consumer,
)
from aos_api.aip_budget_consumer_service import BudgetConsumerRequest
from aos_api.aip_network_issuer_ipc import read_issuer_frame
from aos_api.aip_private_service_transport import require_private_peer


def command():
    return BudgetConsumerRequest(schemaVersion=1, orgId='org-org', projectId='dev-project',
        proposalId='proposal', proposalHash='a'*64, decisionId='decision', bearerToken='aaa.bbb.ccc')


def observed():
    request = command()
    return dict(schemaVersion=1, status='observed', activationEligible=False,
        receipt=dict(resourceType='BudgetRevision', resourceId='budget', revision=2,
            contentHash='b'*64, proposalId=request.proposal_id, proposalHash=request.proposal_hash,
            decisionId=request.decision_id, receiptId='budget-cost-consume-'+request.request_hash))


@pytest.mark.parametrize('method', ['execute_once', 'inquiry'])
@pytest.mark.parametrize('lost', [False, True])
def test_single_frame_without_retry(method, lost):
    left, right = socket.socketpair()
    received = []
    def server():
        with right:
            received.append(json.loads(read_issuer_frame(right)))
            if not lost:
                raw = json.dumps(observed()).encode()
                right.sendall(struct.pack('>I', len(raw))+raw)
    worker = threading.Thread(target=server)
    worker.start()
    with left:
        result = exchange_consumer(left, method, command())
    worker.join(2)
    assert not worker.is_alive() and len(received) == 1
    assert received[0]['method'] == method
    assert result == ({'status': 'unresolved'} if lost else
        {k:v for k,v in observed().items() if k != 'schemaVersion'})


@pytest.mark.parametrize('field,value', [('schemaVersion', True), ('activationEligible', True),
    ('status', 'active'), ('extra', 'untrusted')])
def test_envelope_rejected(field, value):
    reply = {**observed(), field: value}
    with pytest.raises(BudgetConsumerClientBlocked):
        decode_consumer_response(json.dumps(reply).encode(), command())


@pytest.mark.parametrize('field,value', [('resourceType','Other'), ('resourceId','bad id'),
    ('revision',True), ('revision',0), ('revision',9007199254740992), ('contentHash','bad'),
    ('proposalId','other'), ('proposalHash','c'*64), ('decisionId','other'),
    ('receiptId','other'), ('extra','untrusted')])
def test_receipt_bound_to_request(field, value):
    reply = observed()
    reply['receipt'][field] = value
    with pytest.raises(BudgetConsumerClientBlocked):
        decode_consumer_response(json.dumps(reply).encode(), command())


@pytest.mark.parametrize('raw', [b'{"schemaVersion":1,"schemaVersion":1,"status":"unresolved"}',
    b'{"schemaVersion":1,"status":"unresolved","extra":NaN}',
    b'{"schemaVersion":1,"status":"blocked","code":"OTHER"}'])
def test_invalid_json_contract(raw):
    with pytest.raises(BudgetConsumerClientBlocked):
        decode_consumer_response(raw, command())


def test_wrong_peer_and_missing_endpoint_send_nothing():
    endpoint = BudgetConsumerEndpoint(Path('/tmp')/('consumer-missing-'+uuid4().hex),
        os.geteuid(), os.geteuid()+1, os.getegid())
    with pytest.raises(BudgetConsumerClientBlocked):
        request_consumer(endpoint, 'execute_once', command())
    left, right = socket.socketpair()
    with left, right:
        with pytest.raises(ValueError):
            require_private_peer(left, api_uid=endpoint.api_uid,
                service_uid=endpoint.consumer_uid, ipc_gid=endpoint.ipc_gid)
        right.setblocking(False)
        with pytest.raises(BlockingIOError):
            right.recv(1)
