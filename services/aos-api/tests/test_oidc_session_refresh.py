import json
from unittest.mock import Mock
from urllib.parse import parse_qs

import pytest

from aos_api import oidc
from aos_api.errors import ApiError
from aos_api.routers import auth_oidc


@pytest.fixture
def exchange(monkeypatch):
    monkeypatch.setenv('AOS_OIDC_TOKEN_URL', 'http://127.0.0.1:18448/token')
    monkeypatch.setenv('AOS_OIDC_CLIENT_ID', 'aos-api')
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({
        'access_token': 'new-access', 'refresh_token': 'new-refresh', 'expires_in': 300,
    }).encode()
    call = Mock(return_value=response)
    monkeypatch.setattr(oidc.urllib.request, 'urlopen', call)
    return call


def test_refresh_uses_existing_client_and_exact_grant_once(exchange):
    result = auth_oidc.issue_token(auth_oidc.TokenIn(grantType='refresh_token', refreshToken='old-refresh'))
    request = exchange.call_args.args[0]
    assert parse_qs(request.data.decode()) == {
        'grant_type': ['refresh_token'], 'client_id': ['aos-api'], 'refresh_token': ['old-refresh'],
    }
    assert result['accessToken'] == 'new-access'
    assert result['refreshToken'] == 'new-refresh' and result['expiresIn'] == 300
    assert exchange.call_count == 1


def test_password_grant_keeps_original_form(exchange):
    oidc.issue_password_token(username='human', password='private')
    assert parse_qs(exchange.call_args.args[0].data.decode()) == {
        'grant_type': ['password'], 'client_id': ['aos-api'], 'username': ['human'], 'password': ['private'],
    }


def test_refresh_rejection_does_not_echo_secret_or_retry(exchange):
    exchange.side_effect = OSError('private-refresh-secret')
    with pytest.raises(ApiError) as failure:
        auth_oidc.issue_token(auth_oidc.TokenIn(grantType='refresh_token', refreshToken='private-refresh-secret'))
    assert failure.value.status_code == 401
    assert 'private-refresh-secret' not in str(failure.value)
    assert exchange.call_count == 1


@pytest.mark.parametrize('token', [None, ''])
def test_missing_refresh_token_never_calls_idp(exchange, token):
    with pytest.raises(ApiError):
        auth_oidc.issue_token(auth_oidc.TokenIn(grantType='refresh_token', refreshToken=token))
    exchange.assert_not_called()


def test_refresh_disabled_without_original_token_endpoint(exchange, monkeypatch):
    monkeypatch.delenv('AOS_OIDC_TOKEN_URL', raising=False)
    with pytest.raises(ApiError):
        auth_oidc.issue_token(auth_oidc.TokenIn(grantType='refresh_token', refreshToken='private'))
    exchange.assert_not_called()


def test_refresh_input_masks_secret_in_model_representation():
    body = auth_oidc.TokenIn(grantType='refresh_token', refreshToken='private-refresh-secret')
    assert 'private-refresh-secret' not in repr(body)
