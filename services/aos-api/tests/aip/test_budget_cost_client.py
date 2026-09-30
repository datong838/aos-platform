"""Transport-only socketpair proof; production peer gate is tested negatively."""
import json
import os
import socket
import struct
import threading
from pathlib import Path
from uuid import uuid4

import pytest

from aos_api.aip_budget_cost_client import BudgetCostEndpoint, exchange_budget, decode_budget_response, request_budget
from aos_api.aip_budget_cost_issuer import BudgetCostIssuerCommand, BudgetCostIssuerBlocked
from aos_api.aip_network_issuer_ipc import read_issuer_frame
from aos_api.aip_private_service_transport import require_private_peer


def command():
    return BudgetCostIssuerCommand(operation='decide', orgId='org-org', projectId='dev-project',
        bearerToken='synthetic-transport-token', proposalId='proposal', proposalHash='a'*64,
        idempotencyKey='original-key', decision='approved')


def observed():
    return dict(schemaVersion=1, status='observed', activationEligible=False,
        result=dict(decisionId='budget-cost-decision-1', decision='approved', proposalHash='a'*64,
                    activationEligible=False))


@pytest.mark.parametrize('method', ['execute_once', 'inquiry'])
@pytest.mark.parametrize('lost', [False, True])
def test_exact_single_frame_no_resend(method, lost):
    left, right = socket.socketpair()
    received = []
    def server():
        with right:
            received.append(json.loads(read_issuer_frame(right)))
            if not lost:
                body = json.dumps(observed()).encode()
                right.sendall(struct.pack('>I', len(body))+body)
    worker = threading.Thread(target=server); worker.start()
    with left:
        result = exchange_budget(left, method, command())
    worker.join(2)
    assert not worker.is_alive() and len(received) == 1
    assert received[0]['method'] == method
    assert result == ({'status': 'unresolved'} if lost else {k:v for k,v in observed().items() if k!='schemaVersion'})


@pytest.mark.parametrize('field,value', [('schemaVersion', True), ('activationEligible', True),
    ('status', 'active'), ('extra', 'secret')])
def test_bad_response_cannot_claim_observed(field, value):
    value = {**observed(), field: value}
    with pytest.raises(BudgetCostIssuerBlocked):
        decode_budget_response(json.dumps(value).encode(), command())


@pytest.mark.parametrize('field,value', [('decision','rejected'), ('proposalHash','b'*64),
    ('activationEligible',True), ('decisionId','bad id'), ('extra','secret')])
def test_result_bound_to_original_command(field, value):
    reply = observed(); reply['result'][field] = value
    with pytest.raises(BudgetCostIssuerBlocked):
        decode_budget_response(json.dumps(reply).encode(), command())


def test_wrong_peer_and_unconfigured_socket_send_nothing():
    endpoint = BudgetCostEndpoint(Path('/tmp')/('budget-missing-'+uuid4().hex), os.geteuid(), os.geteuid()+1, os.getegid())
    with pytest.raises(BudgetCostIssuerBlocked):
        request_budget(endpoint, 'execute_once', command())
    left, right = socket.socketpair()
    with left, right:
        with pytest.raises(ValueError):
            require_private_peer(left, api_uid=endpoint.api_uid, service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid)
        right.setblocking(False)
        with pytest.raises(BlockingIOError): right.recv(1)
