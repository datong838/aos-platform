"""182m — OTP send/verify HTTP API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api import otp as otp_mod

router = APIRouter(tags=["otp"])


class OtpSendIn(BaseModel):
    channel: str = Field(min_length=1)
    to: str = Field(min_length=1)
    purpose: str = "invite"


class OtpVerifyIn(BaseModel):
    otpId: str = Field(min_length=1)
    code: str = Field(min_length=1)


@router.post("/v1/otp/send")
def otp_send(
    body: OtpSendIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return otp_mod.send_otp(channel=body.channel, to=body.to, purpose=body.purpose)
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc


@router.post("/v1/otp/verify")
def otp_verify(
    body: OtpVerifyIn,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    _ = principal
    try:
        return otp_mod.verify_otp(otp_id=body.otpId, code=body.code)
    except LookupError as exc:
        raise ApiError(code="NOT_FOUND", message=str(exc), status_code=404) from exc
    except ValueError as exc:
        raise ApiError(code="VALIDATION", message=str(exc), status_code=400) from exc
