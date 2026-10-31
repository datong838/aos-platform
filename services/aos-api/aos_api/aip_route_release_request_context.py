"""Request-local Route release authority; never a persisted business contract."""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Header
from pydantic import SecretStr

from aos_api.auth import Principal, parse_bearer, require_principal
from aos_api.oidc import looks_like_jwt


class RouteReleaseRequestContextRejected(ValueError):
    """Safe category that never embeds the token or Authorization header."""


@dataclass(frozen=True)
class RouteReleaseRequestContext:
    principal: Principal
    bearer_token: SecretStr = field(repr=False)

    def __post_init__(self):
        try:
            raw = self.bearer_token.get_secret_value()
            if (type(self.principal) is not Principal
                or self.principal.token_kind != "oidc"
                or (self.principal.org_id, self.principal.project_id)
                    != ("org-org", "dev-project")
                or type(self.bearer_token) is not SecretStr
                or not looks_like_jwt(raw)):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise RouteReleaseRequestContextRejected(
                "current Route release authorization required") from None


def build_route_release_request_context(*, principal: Principal,
        authorization: str | None) -> RouteReleaseRequestContext:
    try:
        token = parse_bearer(authorization)
        return RouteReleaseRequestContext(
            principal=principal, bearer_token=SecretStr(token))
    except RouteReleaseRequestContextRejected:
        raise
    except Exception:
        raise RouteReleaseRequestContextRejected(
            "current Route release authorization required") from None


def require_route_release_request_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_principal),
) -> RouteReleaseRequestContext:
    return build_route_release_request_context(
        principal=principal, authorization=authorization)


def optional_route_release_request_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    principal: Principal = Depends(require_principal),
) -> RouteReleaseRequestContext | None:
    """Carry current Route authority without changing non-Route API semantics."""
    if (type(principal) is not Principal
        or principal.token_kind != "oidc"
        or (principal.org_id, principal.project_id)
            != ("org-org", "dev-project")):
        return None
    return build_route_release_request_context(
        principal=principal, authorization=authorization)
