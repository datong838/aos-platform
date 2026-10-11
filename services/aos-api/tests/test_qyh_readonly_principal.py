from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal, require_principal
from aos_api.routers import auth_oidc


def client(monkeypatch, external=True, kind='oidc'):
    monkeypatch.setenv('AOS_AUTH_EXTERNAL_ONLY', '1' if external else '0')
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV', '0' if external else '1')
    app = FastAPI()
    app.include_router(auth_oidc.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject='private-subject', org_id='org-org', project_id='dev-project',
        roles=['admin'], markings=[], token_kind=kind)
    return TestClient(app)


def test_principal_is_minimal_and_no_membership_route(monkeypatch):
    c = client(monkeypatch)
    response = c.get('/v1/auth/principal')
    assert response.status_code == 200
    assert response.json() == dict(orgId='org-org', projectId='dev-project',
        tokenKind='oidc', authenticated=True, externalOnly=True)
    assert 'private-subject' not in response.text


def test_development_config_refused(monkeypatch):
    assert client(monkeypatch, external=False).get('/v1/auth/principal').status_code == 403


def test_development_principal_refused(monkeypatch):
    assert client(monkeypatch, kind='dev').get('/v1/auth/principal').status_code == 403


def test_route_uses_original_verifier_and_has_no_write_calls():
    import ast
    import inspect
    source = inspect.getsource(auth_oidc.authenticated_principal)
    tree = ast.parse(source)
    calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
    names = {n.id for n in calls if isinstance(n, ast.Name)}
    assert names == {'Depends', 'external_only', 'allow_dev', 'HTTPException'}
    assert require_principal in [d.call for d in next(r for r in auth_oidc.router.routes if r.path == '/v1/auth/principal').dependant.dependencies]
