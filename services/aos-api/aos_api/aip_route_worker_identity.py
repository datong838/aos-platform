"""Short-lived machine OIDC identity for one background Route use.

The client secret is read from one exact macOS Keychain item.  Access tokens
are request-local: this module never caches, persists, refreshes, or logs them.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from aos_api.aip_route_release_request_context import RouteReleaseRequestContext
from aos_api.aip_secret_backend import (
    KeychainLocator,
    SecretClient,
    default_secret_client,
)
from aos_api.auth import resolve_principal
from aos_api.oidc import verify_access_token
from aos_api.tenant_scope import TenantScope

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SERVICE = "com.aos.oidc.route-worker"
_ROLE = "aos_route_worker"
_MAX_TOKEN_LIFETIME_SECONDS = 900


class RouteWorkerIdentityBlocked(RuntimeError):
    """Stable fail-closed category that never contains identity secrets."""


@dataclass(frozen=True)
class RouteWorkerIdentityConfig:
    issuer: str
    audience: str
    token_endpoint: str
    client_id: str
    expected_subject: str
    secret_version: str
    installation_document: Any | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_env(cls) -> RouteWorkerIdentityConfig:
        try:
            if os.environ.get("AOS_AUTH_EXTERNAL_ONLY", "").strip().lower() not in {
                "1",
                "true",
                "yes",
                "on",
            }:
                raise ValueError
            if os.environ.get("AOS_AUTH_ALLOW_DEV", "").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }:
                raise ValueError
            installation_file = os.environ.get(
                "AOS_ROUTE_WORKER_IDENTITY_FILE", ""
            ).strip()
            if installation_file:
                from aos_api.aip_route_worker_installation import (
                    load_route_worker_identity_installation,
                )

                installed = load_route_worker_identity_installation(installation_file)
                values = {
                    "issuer": installed.issuer,
                    "audience": installed.audience,
                    "token_endpoint": installed.tokenEndpoint,
                    "client_id": installed.clientId,
                    "expected_subject": installed.expectedSubject,
                    "secret_version": installed.secretVersion,
                    "installation_document": installed,
                }
                if (
                    os.environ.get("AOS_OIDC_ISSUER", "").strip() != values["issuer"]
                    or os.environ.get("AOS_OIDC_AUDIENCE", "").strip()
                    != values["audience"]
                    or os.environ.get("AOS_OIDC_TOKEN_URL", "").strip()
                    != values["token_endpoint"]
                ):
                    raise ValueError
                return cls(**values)
            return cls.from_control_env()
        except RouteWorkerIdentityBlocked:
            raise
        except Exception:
            raise RouteWorkerIdentityBlocked(
                "ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
            ) from None

    @classmethod
    def from_control_env(cls) -> RouteWorkerIdentityConfig:
        """Read non-secret coordinates even while the installed file is absent."""
        try:
            if os.environ.get("AOS_AUTH_EXTERNAL_ONLY", "").strip().lower() not in {
                "1",
                "true",
                "yes",
                "on",
            }:
                raise ValueError
            if os.environ.get("AOS_AUTH_ALLOW_DEV", "").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }:
                raise ValueError
            values = {
                "issuer": os.environ.get("AOS_OIDC_ISSUER", "").strip(),
                "audience": os.environ.get("AOS_OIDC_AUDIENCE", "").strip(),
                "token_endpoint": os.environ.get("AOS_OIDC_TOKEN_URL", "").strip(),
                "client_id": os.environ.get(
                    "AOS_ROUTE_WORKER_OIDC_CLIENT_ID", ""
                ).strip(),
                "expected_subject": os.environ.get(
                    "AOS_ROUTE_WORKER_OIDC_SUBJECT", ""
                ).strip(),
                "secret_version": os.environ.get(
                    "AOS_ROUTE_WORKER_OIDC_SECRET_VERSION", ""
                ).strip(),
            }
            if not all(values.values()) or any(
                not _SAFE_ID.fullmatch(values[name])
                for name in (
                    "audience",
                    "client_id",
                    "expected_subject",
                    "secret_version",
                )
            ):
                raise ValueError
            issuer = urlsplit(values["issuer"])
            endpoint = urlsplit(values["token_endpoint"])
            expected_path = (
                values["issuer"].rstrip("/") + "/protocol/openid-connect/token"
            )
            loopback = endpoint.hostname in {"127.0.0.1", "::1"}
            if (
                issuer.scheme not in {"http", "https"}
                or endpoint.scheme not in {"http", "https"}
                or (endpoint.scheme != "https" and not loopback)
                or issuer.scheme != endpoint.scheme
                or issuer.hostname != endpoint.hostname
                or issuer.port != endpoint.port
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.query
                or endpoint.fragment
                or values["token_endpoint"] != expected_path
            ):
                raise ValueError
            return cls(**values)
        except RouteWorkerIdentityBlocked:
            raise
        except Exception:
            raise RouteWorkerIdentityBlocked(
                "ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
            ) from None


@dataclass(frozen=True)
class WorkerTokenResponse:
    status_code: int
    payload: Any


class WorkerTokenTransport(Protocol):
    def exchange(self, endpoint: str, form: dict[str, str]) -> WorkerTokenResponse: ...


class HttpWorkerTokenTransport:
    """One bounded token exchange without redirects, proxy inheritance or retry."""

    def exchange(self, endpoint: str, form: dict[str, str]) -> WorkerTokenResponse:
        with httpx.Client(
            timeout=5.0, follow_redirects=False, trust_env=False
        ) as client:
            response = client.post(
                endpoint, data=form, headers={"Accept": "application/json"}
            )
        try:
            payload = response.json()
        except Exception:
            payload = None
        return WorkerTokenResponse(status_code=response.status_code, payload=payload)


class RouteWorkerIdentityProvider:
    def __init__(
        self,
        *,
        config: RouteWorkerIdentityConfig | None = None,
        secret_client: SecretClient | None = None,
        transport: WorkerTokenTransport | None = None,
        installation_authority: Any | None = None,
        clock=time.time,
    ) -> None:
        self.config = config or RouteWorkerIdentityConfig.from_env()
        self._secret_client = secret_client or default_secret_client()
        self._transport = transport or HttpWorkerTokenTransport()
        self._installation_authority = installation_authority
        self._clock = clock

    def _locator(self, scope: TenantScope) -> KeychainLocator:
        raw = (
            f"{_SERVICE}/{scope.org_id}/{scope.project_id}/"
            f"{self.config.client_id}/{self.config.secret_version}"
        )
        return KeychainLocator(
            service=_SERVICE,
            account=(
                f"{scope.org_id}/{scope.project_id}/{self.config.client_id}/"
                f"client-secret/{self.config.secret_version}"
            ),
            ref_fingerprint=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

    def assert_configured(self, scope: TenantScope) -> None:
        """Verify the exact secret version exists without reading its payload."""
        try:
            if type(scope) is not TenantScope or scope.key != (
                "org-org",
                "dev-project",
            ):
                raise ValueError
            if self.config.installation_document is not None:
                authority = self._installation_authority
                if authority is None:
                    from aos_api.aip_route_worker_installation_authority import (
                        CurrentRouteWorkerInstallationAuthority,
                    )

                    authority = CurrentRouteWorkerInstallationAuthority.from_runtime()
                if (
                    authority.assert_current(self.config.installation_document)
                    is not True
                ):
                    raise ValueError
            if not self._secret_client.exists(self._locator(scope)):
                raise ValueError
        except RouteWorkerIdentityBlocked:
            raise
        except Exception:
            raise RouteWorkerIdentityBlocked(
                "ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
            ) from None

    def acquire(self, scope: TenantScope) -> RouteReleaseRequestContext:
        try:
            if type(scope) is not TenantScope or scope.key != (
                "org-org",
                "dev-project",
            ):
                raise ValueError
            secret = self._secret_client.read(self._locator(scope))
            if type(secret) is not str or not secret:
                raise ValueError
            response = self._transport.exchange(
                self.config.token_endpoint,
                {
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": secret,
                },
            )
            if response.status_code != 200 or type(response.payload) is not dict:
                raise ValueError
            token = response.payload.get("access_token")
            expires_in = response.payload.get("expires_in")
            if (
                response.payload.get("token_type") != "Bearer"
                or type(token) is not str
                or token.count(".") != 2
                or type(expires_in) is not int
                or not 30 < expires_in <= _MAX_TOKEN_LIFETIME_SECONDS
            ):
                raise ValueError
            claims = verify_access_token(token)
            now = int(self._clock())
            roles = claims.get("roles")
            if not isinstance(roles, list):
                realm = claims.get("realm_access")
                roles = realm.get("roles") if isinstance(realm, dict) else None
            aud = claims.get("aud")
            audiences = [aud] if isinstance(aud, str) else aud
            if (
                claims.get("sub") != self.config.expected_subject
                or claims.get("iss") != self.config.issuer
                or not isinstance(audiences, list)
                or self.config.audience not in audiences
                or claims.get("org_id") != scope.org_id
                or claims.get("project_id") != scope.project_id
                or not isinstance(roles, list)
                or _ROLE not in roles
                or type(claims.get("exp")) is not int
                or not now + 30 < claims["exp"] <= now + _MAX_TOKEN_LIFETIME_SECONDS
                or type(claims.get("iat")) is not int
                or not now - 30 <= claims["iat"] <= now + 5
            ):
                raise ValueError
            principal = resolve_principal(
                token=token, header_org=scope.org_id, header_project=scope.project_id
            )
            if (
                principal.subject != self.config.expected_subject
                or _ROLE not in principal.roles
                or (principal.org_id, principal.project_id) != scope.key
            ):
                raise ValueError
            return RouteReleaseRequestContext(
                principal=principal, bearer_token=SecretStr(token)
            )
        except RouteWorkerIdentityBlocked:
            raise
        except Exception:
            raise RouteWorkerIdentityBlocked(
                "ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED"
            ) from None
