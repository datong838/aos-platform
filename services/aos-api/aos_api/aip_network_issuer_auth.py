"""External-only identity gate for a future isolated network approval issuer."""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlsplit

from aos_api.auth import Principal, resolve_principal
from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)


class IssuerAuthBlocked(ValueError):
    """A request cannot enter the isolated issuer's DB transaction."""


def _external_https_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or not host
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or host == "localhost" or host.endswith(".localhost")):
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return True
        return ip.is_global
    except ValueError:
        return False


def _configured_urls(single: str, multi: str) -> list[str]:
    value = os.environ.get(multi, "").strip()
    if value:
        return [part.strip() for part in value.split(",")]
    return [os.environ.get(single, "").strip()]


def _require_external_oidc_config() -> None:
    if (os.environ.get("AOS_AUTH_ALLOW_DEV", "").strip() != "0"
            or os.environ.get("AOS_AUTH_EXTERNAL_ONLY", "").strip() != "1"):
        raise IssuerAuthBlocked("ISSUER_EXTERNAL_ONLY_AUTH_REQUIRED")
    issuer_urls = _configured_urls("AOS_OIDC_ISSUER", "AOS_OIDC_ISSUERS")
    jwks_urls = _configured_urls("AOS_OIDC_JWKS_URL", "AOS_OIDC_JWKS_URLS")
    audience = os.environ.get("AOS_OIDC_AUDIENCE", "").strip()
    if (not audience or any(ch.isspace() for ch in audience)
            or not issuer_urls or not jwks_urls
            or not all(_external_https_url(url) for url in (*issuer_urls, *jwks_urls))):
        raise IssuerAuthBlocked("ISSUER_EXTERNAL_OIDC_CONFIG_REQUIRED")


def authenticate_issuer_request(
    request: NetworkIssuerDecisionCommand | NetworkIssuerDecisionInquiry,
) -> Principal:
    """Reverify the JWT on every decision and read-only inquiry, without side effects."""
    if type(request) not in {NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry}:
        raise IssuerAuthBlocked("ISSUER_REQUEST_CONTRACT_REQUIRED")
    _require_external_oidc_config()
    try:
        principal = resolve_principal(
            token=request.bearer_token.get_secret_value(),
            header_org=request.org_id, header_project=request.project_id,
        )
    except Exception:
        raise IssuerAuthBlocked("ISSUER_EXTERNAL_JWT_INVALID") from None
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or principal.org_id != request.org_id or principal.project_id != request.project_id
            or not principal.subject or principal.subject == "unknown"
            or principal.subject != principal.subject.strip()
            or not principal.subject.isprintable()):
        raise IssuerAuthBlocked("ISSUER_PRINCIPAL_TENANT_INVALID")
    return principal
