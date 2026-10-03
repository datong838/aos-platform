"""Revalidate external JWT for each BI issuer command before any DB access."""

from __future__ import annotations

from aos_api.auth import Principal, resolve_principal
from aos_api.aip_bi_plan_issuer_contracts import (
    BIIssuerPrepareCommand, BIIssuerRebindCommand,
)
from aos_api.aip_network_issuer_auth import _require_external_oidc_config


class BIIssuerAuthBlocked(ValueError):
    """No authenticated, tenant-bound issuer actor is available."""


def authenticate_bi_issuer_request(
    command: BIIssuerPrepareCommand | BIIssuerRebindCommand,
) -> Principal:
    """Never accept caller-supplied actor, role or tenant GUC as authority."""
    if type(command) not in (BIIssuerPrepareCommand, BIIssuerRebindCommand):
        raise BIIssuerAuthBlocked("BI_ISSUER_COMMAND_REQUIRED")
    try:
        _require_external_oidc_config()
        principal = resolve_principal(
            token=command.bearer_token.get_secret_value(),
            header_org=command.org_id, header_project=command.project_id,
        )
    except Exception:
        raise BIIssuerAuthBlocked("BI_ISSUER_EXTERNAL_JWT_REQUIRED") from None
    if (type(principal) is not Principal or principal.token_kind != "oidc"
            or (principal.org_id, principal.project_id) != (command.org_id, command.project_id)
            or not principal.subject or principal.subject == "unknown"
            or principal.subject != principal.subject.strip()
            or not principal.subject.isprintable()):
        raise BIIssuerAuthBlocked("BI_ISSUER_PRINCIPAL_TENANT_INVALID")
    return principal
