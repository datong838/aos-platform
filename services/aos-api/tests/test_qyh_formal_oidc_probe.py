import importlib.util
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('qyh_probe', ROOT / 'scripts/ci/probe_qyh_formal_oidc.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

CONFIG = dict(allowDevToken=False, grantTypes=[], jwksConfigured=True,
    jwksUrls=['https://identity.example/jwks'], issuer='https://identity.example', audience='aos-api')
PRINCIPAL = dict(orgId='org-org', projectId='dev-project', tokenKind='oidc', authenticated=True, externalOnly=True)

@pytest.fixture
def server():
    state = dict(config=dict(CONFIG), principal=dict(PRINCIPAL), requests=[])
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            state['requests'].append((self.path, self.headers.get('X-Org-Id')))
            if state.get('redirect'):
                self.send_response(302); self.send_header('Location', 'https://unexpected.example'); self.end_headers(); return
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(state['config'] if self.path.endswith('oidc') else state['principal']).encode())
    http = HTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{http.server_port}',state
    http.shutdown();thread.join();http.server_close()


def token(tmp_path):
    f=tmp_path/'existing-token';f.write_text('aaaa.bbbb.cccc');f.chmod(0o600);return f


def test_protocol_scope_positive(server,tmp_path):
    base,state=server
    r=p.run(base, token(tmp_path), CONFIG['issuer'], CONFIG['audience'])
    assert r['serverAuthenticatedPrincipalScopeMatched'] is True
    assert r['publisherIdentityVerified'] is False
    assert r['runtimeAuthorized'] is False
    assert state['requests']==[('/v1/auth/oidc',None),('/v1/auth/principal','org-org')]
    assert 'aaaa' not in json.dumps(r)

@pytest.mark.parametrize('field,value', [('allowDevToken',True),('jwksConfigured',False),('jwksUrls',[]),('jwksUrls',['http://localhost/jwks']),('issuer','http://aos-dev-oidc'),('grantTypes',['dev'])])
def test_config_refused_before_token(server,field,value,monkeypatch):
    base,state=server;state['config'][field]=value
    monkeypatch.setattr(p,'read_token',lambda *args:pytest.fail('must not read credential'))
    with pytest.raises(p.ProbeError):p.run(base,Path('/missing'),CONFIG['issuer'],CONFIG['audience'])
    assert len(state['requests'])==1

@pytest.mark.parametrize('field,value',[('orgId','dev-org'),('projectId','other'),('tokenKind','dev'),('externalOnly',False),('authenticated',False)])
def test_scope_and_identity_refused(server,tmp_path,field,value):
    base,state=server;state['principal'][field]=value
    with pytest.raises(p.ProbeError):p.run(base,token(tmp_path),CONFIG['issuer'],CONFIG['audience'])


def test_redirect_refused(server):
    base,state=server;state['redirect']=True
    with pytest.raises(p.ProbeError):p.run(base,inspect_only=True)
    assert len(state['requests'])==1


def test_file_permissions_and_symlink(tmp_path):
    f=token(tmp_path);f.chmod(0o644)
    with pytest.raises(p.ProbeError):p.read_token(f)
    f.chmod(0o600);link=tmp_path/'link';link.symlink_to(f)
    with pytest.raises(p.ProbeError):p.read_token(link)

@pytest.mark.parametrize('url',['http://remote.example','https://user:secret@identity.example','http://127.0.0.1?token=secret','http://127.0.0.1/#x'])
def test_api_url_rejected(url):
    with pytest.raises(p.ProbeError):p.api_base(url)
