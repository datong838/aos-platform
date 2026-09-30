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
from tests.aip.test_network_atomic_consumer_pg import counts


@pytest.fixture
def https_signer(tmp_path, monkeypatch):
    host = 'aos-jwks.integration.test'
    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(tls_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=1)).not_valid_after(now + dt.timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
            .sign(tls_key, hashes.SHA256()))
    tls_dir = tmp_path / 'tls'
    tls_dir.mkdir(mode=0o700)
    cert_path, key_path = tls_dir / 'ca.pem', tls_dir / 'key.pem'
    for path, data in ((cert_path, cert.public_bytes(serialization.Encoding.PEM)),
                       (key_path, tls_key.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid='isolated-consumer-key', use='sig', alg='RS256')
    body = json.dumps({'keys': [jwk]}).encode()
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    original_dns = socket.getaddrinfo
    def local_dns(address, *args, **kwargs):
        return original_dns('127.0.0.1' if address == host else address, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', local_dns)
    monkeypatch.setenv('SSL_CERT_FILE', str(cert_path))
    monkeypatch.setenv('NO_PROXY', host + ',127.0.0.1,localhost')
    monkeypatch.setenv('no_proxy', host + ',127.0.0.1,localhost')
    issuer = f'https://{host}:{server.server_port}'
    for key, value in {'AOS_AUTH_ALLOW_DEV': '0', 'AOS_AUTH_EXTERNAL_ONLY': '1',
                       'AOS_OIDC_ISSUER': issuer, 'AOS_OIDC_AUDIENCE': 'isolated-consumer',
                       'AOS_OIDC_JWKS_URL': issuer + '/jwks'}.items():
        monkeypatch.setenv(key, value)
    for key in ('AOS_OIDC_ISSUERS', 'AOS_OIDC_JWKS_URLS'):
        monkeypatch.delenv(key, raising=False)
    thread.start()
    def sign(subject, *, changes=None, omit=None, wrong_key=False):
        claims = {'sub': subject, 'iss': issuer, 'aud': 'isolated-consumer',
                  'exp': int(time.time()) + 120, 'org_id': SCOPE.org_id,
                  'project_id': SCOPE.project_id}
        claims.update(changes or {})
        if omit:
            claims.pop(omit)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if wrong_key else signing_key
        return jwt.encode(claims, key, algorithm='RS256', headers={'kid': jwk['kid']})
    try:
        yield sign, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        key_path.unlink()


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
    monkeypatch.delenv('SSL_CERT_FILE')
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        with pytest.raises(ConsumerAuthBlocked):
            consume_network_once(command_for(args, sign(args[4])), config, attempts)
    assert requests == []
    assert list(attempts.iterdir()) == []
    assert counts(args[2]) == (0, 0, 0)
