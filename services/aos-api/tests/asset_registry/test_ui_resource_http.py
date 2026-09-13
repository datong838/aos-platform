from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.routers import runtime_ui_resources as routes
from .test_ui_resource_reader import case


@pytest.fixture
def client(case, monkeypatch):
    monkeypatch.setenv('AOS_EXTENSION_UI_RESOURCE_ORIGIN', 'http://127.0.0.1:18181')
    monkeypatch.setenv('AOS_EXTENSION_UI_PARENT_ORIGIN', 'http://127.0.0.1:5173')
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_resource_reader] = lambda: case.reader
    with TestClient(app) as client:
        yield client


def url(case):
    return '/v1/bundles/aos/solution.example/1.0.0/frontend/index.html?' + urlencode({
        'packageHash': case.args['package_hash'], 'contentHash': case.args['content_hash']})


def test_real_signed_html_http_without_business_credentials(client, case):
    response = client.get(url(case))
    assert response.status_code == 200
    assert response.content == case.html
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['referrer-policy'] == 'no-referrer'
    csp = response.headers['content-security-policy']
    assert "connect-src 'none'" in csp and 'sandbox allow-scripts' in csp
    assert 'frame-ancestors http://127.0.0.1:5173' in csp
    assert 'allow-same-origin' not in csp and 'unsafe-eval' not in csp
    assert 'set-cookie' not in response.headers


@pytest.mark.parametrize('value', ['', 'https://*.example.com', 'https://@example.com',
    'http://example.com', 'https://example.com/child', 'https://example.com?query=1',
    'https://example.com#frag', 'https://example.com;unsafe', 'https://example.com:bad',
    'https://example.com\n', 'https://%65xample.com'])
def test_parent_config_fail_closed(client, case, monkeypatch, value):
    monkeypatch.setenv('AOS_EXTENSION_UI_PARENT_ORIGIN', value)
    response = client.get(url(case))
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'
    assert case.state.queries == 0


def test_resource_config_required(client, case, monkeypatch):
    monkeypatch.delenv('AOS_EXTENSION_UI_RESOURCE_ORIGIN')
    assert client.get(url(case)).status_code == 503
    assert case.state.queries == 0


@pytest.mark.parametrize('suffix', ['&contentHash=bad', '&packageHash=bad', '&tenant=other'])
def test_extra_and_duplicate_query_refused(client, case, suffix):
    assert client.get(url(case) + suffix).status_code == 400
    assert case.state.queries == 0


def test_missing_query_refused(client, case):
    assert client.get(url(case).split('?')[0]).status_code == 400
    assert case.state.queries == 0


def test_backend_and_unclaimed_html_refused(client, case):
    assert client.get(url(case).replace('frontend/index.html', 'backend/main.py')).status_code == 400
    assert case.state.queries == 0
    assert client.get(url(case).replace('index.html', 'hidden.html')).status_code == 404


def test_revoked_during_read_never_returns_html(client, case):
    def revoke(count):
        if count == 2:
            case.state.rows = []
    case.state.before_query = revoke
    response = client.get(url(case))
    assert response.status_code == 404
    assert case.html not in response.content


def test_unexpected_error_sanitized_and_not_cached(client, case, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError('secret-db-detail')
    monkeypatch.setattr(case.reader, 'read', fail)
    response = client.get(url(case))
    assert response.status_code == 503
    assert 'secret-db-detail' not in response.text
    assert response.headers['cache-control'] == 'no-store'
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
