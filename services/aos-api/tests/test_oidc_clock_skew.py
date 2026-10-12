"""Real RSA/JWKS proof of an explicit small tolerance; default remains strict."""
from datetime import datetime, timezone

import jwt.api_jwt
import pytest

from aos_api.errors import ApiError
from test_oidc_required_claims import signed_request, resolve


@pytest.fixture(autouse=True)
def stable_verifier_clock(monkeypatch):
    fixed = datetime.now(timezone.utc).replace(microsecond=0)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is not None else fixed.replace(tzinfo=None)

    monkeypatch.setattr(jwt.api_jwt, 'datetime', Clock)
    monkeypatch.delenv('AOS_OIDC_LEEWAY_SECONDS', raising=False)
    return int(fixed.timestamp())


def test_explicit_small_clock_skew_accepts_recent_signature(signed_request, monkeypatch, stable_verifier_clock):
    monkeypatch.setenv('AOS_OIDC_LEEWAY_SECONDS', '2')
    principal = resolve(signed_request(changes={'iat': stable_verifier_clock + 1}))
    assert principal.subject == 'isolated-maker'


def test_default_strict_clock_rejects_future_signature(signed_request, stable_verifier_clock):
    with pytest.raises(ApiError):
        resolve(signed_request(changes={'iat': stable_verifier_clock + 1}))


@pytest.mark.parametrize('changes', [{'iat': 3}, {'nbf': 3}, {'exp': -3}])
def test_outside_explicit_bound_is_rejected(signed_request, monkeypatch, stable_verifier_clock, changes):
    monkeypatch.setenv('AOS_OIDC_LEEWAY_SECONDS', '2')
    with pytest.raises(ApiError):
        resolve(signed_request(changes={key: stable_verifier_clock + value for key, value in changes.items()}))


def test_small_expiry_clock_tolerance_is_explicit(signed_request, monkeypatch, stable_verifier_clock):
    monkeypatch.setenv('AOS_OIDC_LEEWAY_SECONDS', '2')
    assert resolve(signed_request(changes={'exp': stable_verifier_clock - 1})).subject == 'isolated-maker'


@pytest.mark.parametrize('value', ['-1', '6', '120', 'nan', '1.5', 'true'])
def test_invalid_explicit_clock_policy_is_rejected(signed_request, monkeypatch, value):
    monkeypatch.setenv('AOS_OIDC_LEEWAY_SECONDS', value)
    with pytest.raises(ApiError):
        resolve(signed_request())


@pytest.mark.parametrize('case', ['wrong_signature', 'wrong_audience', 'missing_sub', 'cross_tenant'])
def test_clock_tolerance_does_not_relax_identity_boundaries(signed_request, monkeypatch, case):
    monkeypatch.setenv('AOS_OIDC_LEEWAY_SECONDS', '2')
    if case == 'wrong_signature':
        token = signed_request(wrong_key=True)
    elif case == 'wrong_audience':
        token = signed_request(changes={'aud': 'other-consumer'})
    elif case == 'missing_sub':
        token = signed_request(omit='sub')
    else:
        token = signed_request(changes={'org_id': 'dev-org'})
    with pytest.raises(ApiError):
        resolve(token)
