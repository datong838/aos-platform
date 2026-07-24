"""TX.3 OIDC-shaped auth — Dev HS256 JWT; Dev RSA JWKS; optional external JWKS URL."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from aos_api.env_load import load_dotenv
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.oidc")

load_dotenv()

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore

_lock = threading.Lock()
_rsa_private_pem: bytes | None = None
_rsa_public_jwk: dict[str, Any] | None = None
_kid = "aos-dev-rsa-1"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def allow_dev() -> bool:
    return _env("AOS_AUTH_ALLOW_DEV", "1").lower() not in {"0", "false", "no", "off"}


def issuer() -> str:
    return _env("AOS_OIDC_ISSUER", "http://aos-dev-oidc")


def audience() -> str:
    return _env("AOS_OIDC_AUDIENCE", "aos-api")


def dev_secret() -> str:
    return _env(
        "AOS_OIDC_DEV_SECRET",
        "aos_dev_oidc_hs256_change_me_32b!",
    )


def jwks_url() -> str:
    return _env("AOS_OIDC_JWKS_URL")


def jwks_urls() -> list[str]:
    """Prefer AOS_OIDC_JWKS_URLS (comma) for HA failover; else single JWKS URL."""
    multi = _env("AOS_OIDC_JWKS_URLS")
    if multi:
        return [u.strip() for u in multi.split(",") if u.strip()]
    single = jwks_url()
    return [single] if single else []


def issuers() -> list[str]:
    multi = _env("AOS_OIDC_ISSUERS")
    if multi:
        return [u.strip() for u in multi.split(",") if u.strip()]
    return [issuer()]


def token_url() -> str:
    """Optional IdP token endpoint (Keycloak password grant proxy)."""
    return _env("AOS_OIDC_TOKEN_URL")


def client_id() -> str:
    return _env("AOS_OIDC_CLIENT_ID", "aos-api")


def client_id_ref() -> str:
    return _env("AOS_OIDC_CLIENT_ID_REF", "vault:secret/data/aos/oidc#client_id")


def prefer_rs256() -> bool:
    return _env("AOS_OIDC_TOKEN_ALG", "HS256").upper() == "RS256"


def _ensure_rsa() -> None:
    """Dev-shaped RSA keypair for local JWKS (swap URL for real Keycloak)."""
    global _rsa_private_pem, _rsa_public_jwk
    if _rsa_private_pem and _rsa_public_jwk:
        return
    with _lock:
        if _rsa_private_pem and _rsa_public_jwk:
            return
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("cryptography required for RS256/JWKS") from exc

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _rsa_private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        assert jwt is not None
        from jwt.algorithms import RSAAlgorithm

        jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
        jwk["kid"] = _kid
        jwk["use"] = "sig"
        jwk["alg"] = "RS256"
        _rsa_public_jwk = jwk
        log.info("oidc_dev_rsa_ready kid=%s", _kid)


def local_jwks() -> dict[str, Any]:
    _ensure_rsa()
    assert _rsa_public_jwk is not None
    return {"keys": [_rsa_public_jwk]}


def public_config() -> dict[str, Any]:
    grants = ["dev"]
    if token_url():
        grants.append("password")
    urls = jwks_urls()
    return {
        "issuer": issuer(),
        "issuers": issuers(),
        "audience": audience(),
        "clientIdRef": client_id_ref(),
        "jwksConfigured": bool(urls) or True,
        "jwksUrlHint": (urls[0] if urls else None) or "/v1/auth/jwks",
        "jwksUrls": urls,
        "haMode": len(urls) > 1,
        "tokenUrlConfigured": bool(token_url()),
        "allowDevToken": allow_dev(),
        "tokenEndpoint": "/v1/auth/token",
        "tokenAlgDefault": "RS256" if prefer_rs256() else "HS256",
        "grantTypes": grants,
        "note": (
            "Set AOS_OIDC_JWKS_URL or AOS_OIDC_JWKS_URLS (HA failover); "
            "optional AOS_OIDC_TOKEN_URL for password grant; profile oidc-ha for Dev dual KC"
        ),
    }


def issue_password_token(
    *,
    username: str,
    password: str,
) -> dict[str, Any]:
    """Proxy Resource Owner Password to IdP (Dev Keycloak). Never log password."""
    url = token_url()
    if not url:
        raise ValueError("AOS_OIDC_TOKEN_URL not configured")
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": client_id(),
            "username": username,
            "password": password,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        log.warning("oidc_password_grant_fail err=%s", type(exc).__name__)
        raise ValueError(f"IdP token failed: {exc}") from exc
    access = raw.get("access_token")
    if not access:
        raise ValueError("IdP response missing access_token")
    return {
        "accessToken": access,
        "tokenType": raw.get("token_type") or "Bearer",
        "expiresIn": int(raw.get("expires_in") or 3600),
        "issuer": issuer(),
        "tokenKind": "oidc-keycloak",
        "alg": "RS256",
        "refreshToken": raw.get("refresh_token"),
    }


def issue_dev_token(
    *,
    subject: str = "alice",
    org_id: str = "dev-org",
    project_id: str = "dev-project",
    roles: list[str] | None = None,
    markings: list[str] | None = None,
    ttl_sec: int = 3600,
    alg: str | None = None,
) -> dict[str, Any]:
    if jwt is None:
        raise RuntimeError("PyJWT not installed")
    now = int(time.time())
    payload = {
        "sub": subject,
        "iss": issuer(),
        "aud": audience(),
        "iat": now,
        "exp": now + ttl_sec,
        "org_id": org_id,
        "project_id": project_id,
        "roles": roles or ["developer"],
        "markings": markings or ["public", "restricted"],
        "token_use": "access",
    }
    use_alg = (alg or ("RS256" if prefer_rs256() else "HS256")).upper()
    if use_alg == "RS256":
        _ensure_rsa()
        assert _rsa_private_pem is not None
        token = jwt.encode(
            payload,
            _rsa_private_pem,
            algorithm="RS256",
            headers={"kid": _kid},
        )
        kind = "oidc-rs256"
    else:
        token = jwt.encode(payload, dev_secret(), algorithm="HS256")
        kind = "oidc"
    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresIn": ttl_sec,
        "issuer": issuer(),
        "tokenKind": kind,
        "alg": use_alg,
    }


def _verify_hs256(token: str) -> dict[str, Any]:
    assert jwt is not None
    return jwt.decode(
        token,
        dev_secret(),
        algorithms=["HS256"],
        audience=audience(),
        issuer=issuers(),
    )


def _verify_local_rs256(token: str) -> dict[str, Any]:
    assert jwt is not None
    _ensure_rsa()
    assert _rsa_private_pem is not None
    from cryptography.hazmat.primitives import serialization

    priv = serialization.load_pem_private_key(_rsa_private_pem, password=None)
    pub = priv.public_key()
    return jwt.decode(
        token,
        pub,
        algorithms=["RS256"],
        audience=audience(),
        issuer=issuers(),
    )


def _verify_jwks(token: str) -> dict[str, Any]:
    assert jwt is not None
    urls = jwks_urls()
    if not urls:
        raise ValueError("no JWKS URL configured")
    from jwt import PyJWKClient

    last_exc: Exception | None = None
    for url in urls:
        try:
            client = PyJWKClient(url)
            key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                audience=audience(),
                issuer=issuers(),
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("jwks_failover url=%s err=%s", url, type(exc).__name__)
    assert last_exc is not None
    raise last_exc


def looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and len(token) > 20


def verify_access_token(token: str) -> dict[str, Any]:
    if jwt is None:
        raise ValueError("PyJWT not installed")
    header = jwt.get_unverified_header(token)
    alg = str(header.get("alg") or "HS256").upper()
    if alg in {"RS256", "ES256"}:
        if jwks_urls():
            try:
                return _verify_jwks(token)
            except Exception as exc:  # noqa: BLE001
                log.warning("jwks_url_verify_fail err=%s; try local JWKS", exc)
        return _verify_local_rs256(token)
    return _verify_hs256(token)
