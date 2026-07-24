"""W2-BK · SSL / Health Snooze / Context Panel / Marketplace 路由（#10 #11 #12 #13）."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.ssl_health_snooze_marketplace import (
    ContextEntry,
    HealthCheckProduct,
    SnoozeHistoryEntry,
    SnoozeRecord,
    SslCertificate,
    SslHealthSnoozeError,
    get_health_context_panel_engine,
    get_health_marketplace_engine,
    get_health_snooze_engine,
    get_ssl_certificate_engine,
)

router = APIRouter(
    prefix="/ssl-health-snooze-marketplace",
    tags=["ssl-health-snooze-marketplace"],
)


def _map_err(err: SslHealthSnoozeError) -> HTTPException:
    code = getattr(err, "code", "") or ""
    if code == "NOT_FOUND":
        status = 404
    elif code.startswith("INVALID_"):
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": code, "message": str(err)}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ #10 SSL Certificates ════════════════════

class RegisterCertBody(BaseModel):
    agent_id: str
    common_name: str
    valid_from: float = 0
    valid_until: float = 0
    issuer: str = ""
    serial_number: str = ""
    fingerprint: str = ""
    auto_renew: bool = False


class RenewCertBody(BaseModel):
    new_valid_until: float


@router.post("/ssl/certs", response_model=SslCertificate)
def register_cert(body: RegisterCertBody, _=require_principal):
    try:
        return get_ssl_certificate_engine().register_cert(
            agent_id=body.agent_id,
            common_name=body.common_name,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            issuer=body.issuer,
            serial_number=body.serial_number,
            fingerprint=body.fingerprint,
            auto_renew=body.auto_renew,
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/ssl/certs/{cert_id}", response_model=SslCertificate)
def get_cert(cert_id: str, _=require_principal):
    try:
        return get_ssl_certificate_engine().get_cert(cert_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/ssl/certs", response_model=list[SslCertificate])
def list_certs(
    agent_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_ssl_certificate_engine().list_certs(agent_id=agent_id, status=status)


@router.put("/ssl/certs/{cert_id}", response_model=SslCertificate)
def update_cert(cert_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_ssl_certificate_engine().update_cert(cert_id, updates)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/ssl/certs/{cert_id}/revoke", response_model=SslCertificate)
def revoke_cert(cert_id: str, _=require_principal):
    try:
        return get_ssl_certificate_engine().revoke_cert(cert_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/ssl/certs/{cert_id}/check-expiry")
def check_expiry(cert_id: str, _=require_principal):
    try:
        return get_ssl_certificate_engine().check_expiry(cert_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/ssl/certs/{cert_id}/renew", response_model=SslCertificate)
def renew_cert(cert_id: str, body: RenewCertBody, _=require_principal):
    try:
        return get_ssl_certificate_engine().renew_cert(cert_id, body.new_valid_until)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.delete("/ssl/certs/{cert_id}")
def delete_cert(cert_id: str, _=require_principal):
    deleted = get_ssl_certificate_engine().delete_cert(cert_id)
    return {"deleted": deleted}


# ════════════════════ #11 Health Snooze ════════════════════

class SnoozeBody(BaseModel):
    check_id: str
    snoozed_by: str
    duration_seconds: int
    reason: str = ""


class BatchSnoozeBody(BaseModel):
    check_ids: list[str]
    snoozed_by: str
    duration_seconds: int
    reason: str = ""


class UnsnoozeBody(BaseModel):
    by_user: str


@router.post("/snooze", response_model=SnoozeRecord)
def snooze(body: SnoozeBody, _=require_principal):
    try:
        return get_health_snooze_engine().snooze(
            check_id=body.check_id,
            snoozed_by=body.snoozed_by,
            duration_seconds=body.duration_seconds,
            reason=body.reason,
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/snooze/batch", response_model=list[SnoozeRecord])
def batch_snooze(body: BatchSnoozeBody, _=require_principal):
    try:
        return get_health_snooze_engine().batch_snooze(
            check_ids=body.check_ids,
            snoozed_by=body.snoozed_by,
            duration_seconds=body.duration_seconds,
            reason=body.reason,
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/snooze/{check_id}/unsnooze")
def unsnooze(check_id: str, body: UnsnoozeBody, _=require_principal):
    try:
        ok = get_health_snooze_engine().unsnooze(check_id, body.by_user)
        return {"unsnoozed": ok}
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/snooze/active/{check_id}", response_model=Optional[SnoozeRecord])
def get_active_snooze(check_id: str, _=require_principal):
    return get_health_snooze_engine().get_active_snooze(check_id)


@router.get("/snooze", response_model=list[SnoozeRecord])
def list_snoozes(
    check_id: str | None = Query(None),
    include_expired: bool = Query(False),
    _=require_principal,
):
    return get_health_snooze_engine().list_snoozes(
        check_id=check_id, include_expired=include_expired
    )


@router.get("/snooze/history", response_model=list[SnoozeHistoryEntry])
def list_snooze_history(
    check_id: str | None = Query(None),
    _=require_principal,
):
    return get_health_snooze_engine().list_history(check_id=check_id)


@router.post("/snooze/cleanup-expired")
def cleanup_expired(_=require_principal):
    count = get_health_snooze_engine().cleanup_expired()
    return {"removed": count}


@router.delete("/snooze/{snooze_id}")
def delete_snooze(snooze_id: str, _=require_principal):
    deleted = get_health_snooze_engine().delete_snooze(snooze_id)
    return {"deleted": deleted}


# ════════════════════ #12 Health Context Panel ════════════════════

class AddEntryBody(BaseModel):
    check_id: str
    entry_type: str
    content: str
    author: str
    metadata: dict[str, Any] | None = None


class UpdateEntryBody(BaseModel):
    content: str | None = None
    metadata: dict[str, Any] | None = None


@router.post("/context/entries", response_model=ContextEntry)
def add_entry(body: AddEntryBody, _=require_principal):
    try:
        return get_health_context_panel_engine().add_entry(
            check_id=body.check_id,
            entry_type=body.entry_type,
            content=body.content,
            author=body.author,
            metadata=body.metadata,
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/context/entries/{entry_id}", response_model=ContextEntry)
def get_entry(entry_id: str, _=require_principal):
    try:
        return get_health_context_panel_engine().get_entry(entry_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/context/entries", response_model=list[ContextEntry])
def list_entries(
    check_id: str | None = Query(None),
    entry_type: str | None = Query(None),
    _=require_principal,
):
    return get_health_context_panel_engine().list_entries(
        check_id=check_id, entry_type=entry_type
    )


@router.put("/context/entries/{entry_id}", response_model=ContextEntry)
def update_entry(entry_id: str, body: UpdateEntryBody, _=require_principal):
    try:
        return get_health_context_panel_engine().update_entry(
            entry_id, content=body.content, metadata=body.metadata
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.delete("/context/entries/{entry_id}")
def delete_entry(entry_id: str, _=require_principal):
    deleted = get_health_context_panel_engine().delete_entry(entry_id)
    return {"deleted": deleted}


@router.get("/context/summary/{check_id}")
def get_context_summary(check_id: str, _=require_principal):
    return get_health_context_panel_engine().get_context_summary(check_id)


# ════════════════════ #13 Health Marketplace ════════════════════

class IntegrateCheckBody(BaseModel):
    check_id: str
    product_id: str
    product_name: str
    check_name: str
    check_description: str = ""
    severity_level: str = "info"


@router.post("/marketplace/integrate", response_model=HealthCheckProduct)
def integrate_check(body: IntegrateCheckBody, _=require_principal):
    try:
        return get_health_marketplace_engine().integrate_check(
            check_id=body.check_id,
            product_id=body.product_id,
            product_name=body.product_name,
            check_name=body.check_name,
            check_description=body.check_description,
            severity_level=body.severity_level,
        )
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/marketplace/{product_id}", response_model=HealthCheckProduct)
def get_product(product_id: str, _=require_principal):
    try:
        return get_health_marketplace_engine().get_product(product_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.get("/marketplace", response_model=list[HealthCheckProduct])
def list_products(
    product_id: str | None = Query(None),
    check_id: str | None = Query(None),
    severity_level: str | None = Query(None),
    _=require_principal,
):
    return get_health_marketplace_engine().list_products(
        product_id=product_id,
        check_id=check_id,
        severity_level=severity_level,
    )


@router.put("/marketplace/{product_id}", response_model=HealthCheckProduct)
def update_product(product_id: str, updates: dict[str, Any], _=require_principal):
    try:
        return get_health_marketplace_engine().update_product(product_id, updates)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/marketplace/{product_id}/enable", response_model=HealthCheckProduct)
def enable_product(product_id: str, _=require_principal):
    try:
        return get_health_marketplace_engine().enable_product(product_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.post("/marketplace/{product_id}/disable", response_model=HealthCheckProduct)
def disable_product(product_id: str, _=require_principal):
    try:
        return get_health_marketplace_engine().disable_product(product_id)
    except SslHealthSnoozeError as e:
        raise _map_err(e) from e


@router.delete("/marketplace/{product_id}")
def delete_product(product_id: str, _=require_principal):
    deleted = get_health_marketplace_engine().delete_product(product_id)
    return {"deleted": deleted}
