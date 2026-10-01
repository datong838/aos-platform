"""Isolated TLS/JWT/PG integration, never formal customer identity acceptance."""
import datetime as dt
import json
import os
import socket
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jwt.algorithms import RSAAlgorithm

from aos_api.aip_network_consumer_auth import ConsumerAuthBlocked
from aos_api.aip_network_consumer_connection import ConsumerDatabaseBlocked
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_consumer_service import consume_network_once, inquire_network
from tests.aip.test_network_consumer_actor_pg import approved_args
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip._runtime_guard_history_fixture import https_signer
from tests.aip.test_network_atomic_consumer_pg import counts




def command_for(args, token):
    return NetworkConsumerCommand.model_validate({
        'schemaVersion': 1, 'bearerToken': token, 'orgId': args[0], 'projectId': args[1],
        'proposalId': args[2], 'approvalEventId': args[3], 'proposalHash': args[5],
        'targetContentHash': args[6], 'bindingHash': args[7],
    })


def test_signed_identity_consumes_and_refreshed_token_observes(private_passfile, tmp_path, https_signer):
    args, _ = approved_args()
    sign, requests = https_signer
    command = command_for(args, sign(args[4]))
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        result = consume_network_once(command, config, attempts)
        assert result['status'] == 'observed'
        refreshed = command_for(args, sign(args[4], changes={'jti': 'new-token'}))
        assert inquire_network(refreshed.inquiry(), config) == result
        assert consume_network_once(refreshed, config, attempts) == result
    assert len(requests) >= 3
    assert len(list(attempts.iterdir())) == 1
    assert counts(args[2]) == (1, 1, 1)


@pytest.mark.parametrize('bad', ['expired', 'no_exp', 'wrong_signature', 'wrong_audience', 'cross_tenant', 'wrong_actor'])
def test_signed_invalid_authority_never_reserves_or_writes(private_passfile, tmp_path, https_signer, bad):
    args, _ = approved_args()
    sign, requests = https_signer
    changes = {'expired': {'exp': 1}, 'wrong_audience': {'aud': 'other'},
               'cross_tenant': {'org_id': 'other-org'}}.get(bad)
    token = sign('different-maker' if bad == 'wrong_actor' else args[4],
                 changes=changes, omit='exp' if bad == 'no_exp' else None,
                 wrong_key=bad == 'wrong_signature')
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        with pytest.raises(ConsumerDatabaseBlocked if bad == 'wrong_actor' else ConsumerAuthBlocked):
            consume_network_once(command_for(args, token), config, attempts)
    assert requests
    assert list(attempts.iterdir()) == []
    assert counts(args[2]) == (0, 0, 0)


def test_valid_signed_identity_cannot_bypass_current_member_revocation(private_passfile, tmp_path, https_signer):
    args, _ = approved_args()
    sign, _ = https_signer
    command = command_for(args, sign(args[4]))
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        assert consume_network_once(command, config, attempts)['status'] == 'observed'
        with isolated_owner() as conn:
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                         (*SCOPE.key, args[4]))
        with pytest.raises(ConsumerDatabaseBlocked):
            inquire_network(command.inquiry(), config)
    assert counts(args[2]) == (1, 1, 1)


def test_untrusted_tls_certificate_is_not_bypassed(private_passfile, tmp_path, https_signer, monkeypatch):
    args, _ = approved_args()
    sign, requests = https_signer
    requests_before = list(requests)  # Guard sources now perform real signed preparation.
    monkeypatch.delenv('SSL_CERT_FILE')
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        with pytest.raises(ConsumerAuthBlocked):
            consume_network_once(command_for(args, sign(args[4])), config, attempts)
    assert requests == requests_before
    assert list(attempts.iterdir()) == []
    assert counts(args[2]) == (0, 0, 0)
