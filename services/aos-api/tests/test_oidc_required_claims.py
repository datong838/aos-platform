"""Real RSA/JWKS HTTP verification; isolated keys are not formal identity proof."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from aos_api.auth import resolve_principal


@pytest.fixture
def signed_request(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid='isolated-required-claims', use='sig', alg='RS256')
    body = json.dumps({'keys': [jwk]}).encode()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV', '0')
    monkeypatch.setenv('AOS_AUTH_EXTERNAL_ONLY', '1')
    monkeypatch.setenv('AOS_OIDC_ISSUER', 'https://isolated-identity.example.test')
    monkeypatch.setenv('AOS_OIDC_AUDIENCE', 'isolated-consumer')
    monkeypatch.setenv('AOS_OIDC_JWKS_URL', f'http://127.0.0.1:{server.server_port}/jwks')
    monkeypatch.delenv('AOS_OIDC_ISSUERS', raising=False)
    monkeypatch.delenv('AOS_OIDC_JWKS_URLS', raising=False)
    def token(*, omit=None, changes=None, wrong_key=False):
        claims = {'sub': 'isolated-maker', 'iss': 'https://isolated-identity.example.test',
                  'aud': 'isolated-consumer', 'exp': int(time.time()) + 120,
                  'org_id': 'org-org', 'project_id': 'dev-project'}
        claims.update(changes or {})
        if omit:
            claims.pop(omit)
        signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if wrong_key else key
        return jwt.encode(claims, signing_key, algorithm='RS256', headers={'kid': jwk['kid']})
    try:
        yield token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def resolve(token):
    return resolve_principal(token=token, header_org='org-org', header_project='dev-project')


def test_signed_expiring_identity_resolves(signed_request):
    principal = resolve(signed_request())
    assert principal.subject == 'isolated-maker'
    assert (principal.org_id, principal.project_id, principal.token_kind) == ('org-org', 'dev-project', 'oidc')


@pytest.mark.parametrize('claim', ['exp', 'sub', 'iss', 'aud'])
def test_required_claim_cannot_be_omitted(signed_request, claim):
    from aos_api.errors import ApiError
    with pytest.raises(ApiError):
        resolve(signed_request(omit=claim))


@pytest.mark.parametrize('changes', [{'exp': 1}, {'aud': 'other'}, {'iss': 'https://other.example.test'}, {'org_id': 'other-org'}])
def test_expiry_and_binding_remain_enforced(signed_request, changes):
    from aos_api.errors import ApiError
    with pytest.raises(ApiError):
        resolve(signed_request(changes=changes))


def test_wrong_signature_rejected(signed_request):
    from aos_api.errors import ApiError
    with pytest.raises(ApiError):
        resolve(signed_request(wrong_key=True))
