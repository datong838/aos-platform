"""Keep original budget review requests before one dispatch; PG remains authority."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

from aos_api.aip_budget_activation_contracts import (
    CreateBudgetActivationPreviewRequest, DecideBudgetActivationRequest,
    RevokeBudgetActivationDecisionRequest,
)
from aos_api.aip_budget_activation_store import (
    AipBudgetActivationStore, BudgetActivationDenied, _identity, _member, _require_inquiry_connection,
)
from aos_api.aip_budget_contracts import BudgetLifecycle
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_network_issuer_attempt import _private_directory_fd, _read_marker
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.auth import Principal, parse_bearer, resolve_principal
from aos_api.db import connect_read_only
from aos_api.aip_private_request_file import create_private_request_file


class BudgetProductBlocked(ValueError):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.status_code = status_code


@dataclass(frozen=True)
class BudgetRequestRef:
    operation: str
    resource_id: str
    revision: int | None = None
    head_version: int | None = None

    def __post_init__(self):
        if (self.operation not in {"preview", "decision", "revoke"}
                or type(self.resource_id) is not str or not 1 <= len(self.resource_id) <= 160
                or self.resource_id != self.resource_id.strip() or not self.resource_id.isprintable()):
            raise BudgetProductBlocked("BUDGET_PRODUCT_REF_INVALID", 422)
        if self.operation == "preview":
            if (type(self.revision) is not int or self.revision < 2
                    or type(self.head_version) is not int or self.head_version < 1):
                raise BudgetProductBlocked("BUDGET_PRODUCT_REF_INVALID", 422)
        elif self.revision is not None or self.head_version is not None:
            raise BudgetProductBlocked("BUDGET_PRODUCT_REF_INVALID", 422)


def _authenticated(principal, authorization):
    try:
        _require_external_oidc_config()
        if type(principal) is not Principal or principal.token_kind != "oidc":
            raise ValueError()
        verified = resolve_principal(token=parse_bearer(authorization),
            header_org=principal.org_id, header_project=principal.project_id)
        scope, actor = _identity(verified)
        if (actor == "unknown" or not actor.isprintable() or
                (actor, *scope.key) != (principal.subject, principal.org_id, principal.project_id)):
            raise ValueError()
    except Exception:
        raise BudgetProductBlocked("BUDGET_PRODUCT_IDENTITY_REQUIRED", 403) from None
    try:
        with connect_read_only(scope) as conn:
            _require_inquiry_connection(conn, scope)
            _member(conn, scope, actor, label="REVIEWER", lock=False)
    except BudgetActivationDenied:
        raise
    except Exception:
        raise BudgetProductBlocked("BUDGET_PRODUCT_MEMBER_UNAVAILABLE", 503) from None
    return verified


def _directory(directory):
    if directory is None or not Path(directory).is_absolute():
        raise BudgetProductBlocked("BUDGET_PRODUCT_DIRECTORY_REQUIRED", 503)
    return _private_directory_fd(Path(directory))


def _slot(principal, ref):
    if type(ref) is not BudgetRequestRef:
        raise BudgetProductBlocked("BUDGET_PRODUCT_REF_INVALID", 422)
    ref.__post_init__()
    return "budget-product-v1-"+canonical_hash([
        principal.org_id, principal.project_id, principal.subject,
        ref.operation, ref.resource_id, ref.revision, ref.head_version])


def _envelope(principal, ref, body):
    models = {"preview": CreateBudgetActivationPreviewRequest,
              "decision": DecideBudgetActivationRequest, "revoke": RevokeBudgetActivationDecisionRequest}
    if type(body) is not models[ref.operation]:
        raise ValueError("invalid request type")
    request = body.model_dump(mode="json", by_alias=True)
    # Revalidate model_copy inputs too; storage never trusts a constructed model.
    models[ref.operation].model_validate(request)
    if ref.operation == "preview" and (
            body.target.budget_id != ref.resource_id or body.target.revision != ref.revision
            or body.target.lifecycle is not BudgetLifecycle.ACTIVE
            or body.checker_subject == principal.subject):
        raise ValueError("preview source mismatch")
    return {"schemaVersion": 1, "state": "ATTEMPTED", "key": _slot(principal, ref),
        "orgId": principal.org_id, "projectId": principal.project_id, "subject": principal.subject,
        "operation": ref.operation, "resourceId": ref.resource_id,
        "revision": ref.revision, "headVersion": ref.head_version,
        "requestHash": canonical_hash(request), "request": request}


def _read(fd, key, principal, ref):
    saved = _read_marker(fd, key+".json", allow_missing=True)
    if saved is None:
        return None
    model = {"preview": CreateBudgetActivationPreviewRequest,
             "decision": DecideBudgetActivationRequest, "revoke": RevokeBudgetActivationDecisionRequest}[ref.operation]
    body = model.model_validate(saved["request"])
    if (type(saved.get("schemaVersion")) is not int
            or (ref.operation == "preview" and (type(saved.get("revision")) is not int
                                                or type(saved.get("headVersion")) is not int))
            or saved != _envelope(principal, ref, body)):
        raise ValueError("saved request mismatch")
    return body


def _call(store, ref, body, principal, key, *, inquiry):
    if ref.operation == "preview":
        call = store.inquire_preview if inquiry else store.create_preview
        return call(principal, body.target, body.checker_subject, key, expected_head_version=ref.head_version)
    if ref.operation == "decision":
        call = store.inquire_decision if inquiry else store.decide
        return call(principal, ref.resource_id, key, decision=body.decision)
    call = store.inquire_revocation if inquiry else store.revoke
    return call(principal, ref.resource_id, key, reason=body.reason)


def inquire_request(directory, ref, principal, authorization):
    verified = _authenticated(principal, authorization)
    key = _slot(verified, ref)
    try:
        fd = _directory(directory)
        try:
            body = _read(fd, key, verified, ref)
        finally:
            os.close(fd)
    except BudgetProductBlocked:
        raise
    except Exception:
        raise BudgetProductBlocked("BUDGET_PRODUCT_SAVED_REQUEST_UNTRUSTED", 503) from None
    return ({"status": "not_attempted"} if body is None else
            _call(AipBudgetActivationStore(), ref, body, verified, key, inquiry=True))


def submit_request(directory, ref, body, principal, authorization):
    verified = _authenticated(principal, authorization)
    key = _slot(verified, ref)
    try:
        envelope = _envelope(verified, ref, body)
        raw = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > 4096:
            raise ValueError("saved request too large")
    except Exception:
        raise BudgetProductBlocked("BUDGET_PRODUCT_REQUEST_INVALID", 422) from None
    reserved = False
    try:
        directory_fd = _directory(directory)
        try:
            prior = _read(directory_fd, key, verified, ref)
            if prior is None:
                reserved = create_private_request_file(directory_fd, key+".json", raw)
                if not reserved:
                    prior = _read(directory_fd, key, verified, ref)
                    if prior is None:
                        raise ValueError("reservation disappeared")
            if prior is not None and _envelope(verified, ref, prior) != envelope:
                raise BudgetProductBlocked("BUDGET_PRODUCT_REQUEST_CONFLICT", 409)
        finally:
            os.close(directory_fd)
    except BudgetProductBlocked:
        raise
    except Exception:
        raise BudgetProductBlocked("BUDGET_PRODUCT_SAVED_REQUEST_UNTRUSTED", 503) from None
    store = AipBudgetActivationStore()
    if reserved:
        try:
            _call(store, ref, body, verified, key, inquiry=False)
        except Exception:
            # A lost response never proves rollback; retain the durable reservation.
            pass
    return _call(store, ref, body, verified, key, inquiry=True)
