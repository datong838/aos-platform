"""O1-R3 installation-bound ontology overlay API."""

from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_overlay import list_overlays, put_overlay
from aos_api.tenant_scope import TenantScope

router = APIRouter(tags=["ontology-overlay"])
_PROPERTY_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,127}$")


class ExtendedProperty(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["string", "integer", "number", "boolean", "datetime", "json"]
    nullable: bool = True
    description: str = Field(default="", max_length=1000)


class OverlayPolicies(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: Literal[1]
    readRoles: list[str] = Field(default_factory=list, max_length=100)
    writeRoles: list[str] = Field(default_factory=list, max_length=100)
    masking: dict[str, Any] = Field(default_factory=dict)
    retentionDays: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("readRoles", "writeRoles")
    @classmethod
    def roles_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("roles must be non-empty and unique")
        return value


class OntologyOverlayPutDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["override", "inherit"]
    displayName: str | None = Field(default=None, min_length=1, max_length=240)
    visibleProperties: list[str] | None = Field(default=None, max_length=500)
    extendedProperties: dict[str, ExtendedProperty] = Field(default_factory=dict)
    policies: OverlayPolicies | None = None

    @field_validator("visibleProperties")
    @classmethod
    def visible_is_unique(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (len(value) != len(set(value)) or any(not item.strip() for item in value)):
            raise ValueError("visibleProperties must be non-empty and unique")
        return value

    @field_validator("extendedProperties")
    @classmethod
    def extended_names_are_valid(cls, value: dict[str, ExtendedProperty]) -> dict[str, ExtendedProperty]:
        if len(value) > 200 or any(_PROPERTY_NAME.fullmatch(key) is None for key in value):
            raise ValueError("extended property names are invalid or exceed the limit")
        return value

    @model_validator(mode="after")
    def inherit_has_no_override(self) -> "OntologyOverlayPutDTO":
        if self.mode == "inherit" and (
            self.displayName is not None
            or self.visibleProperties is not None
            or self.extendedProperties
            or self.policies is not None
        ):
            raise ValueError("inherit mode cannot contain override fields")
        if self.mode == "override" and self.displayName is None:
            raise ValueError("override mode requires displayName")
        return self


@router.put("/v1/ontology/installations/{installation_pk}/overlays/{target_kind}/{target_id}")
def update_overlay(
    installation_pk: str,
    target_kind: Literal["ObjectType", "LinkType"],
    target_id: str,
    body: OntologyOverlayPutDTO,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    if not if_match:
        raise ApiError(code="ONTOLOGY_OVERLAY_IF_MATCH_REQUIRED", message="If-Match is required", status_code=428)
    if not idempotency_key or not idempotency_key.strip() or len(idempotency_key) > 240:
        raise ApiError(code="IDEMPOTENCY_KEY_REQUIRED", message="valid Idempotency-Key is required", status_code=400)
    scope = TenantScope(principal.org_id, principal.project_id)
    payload = body.model_dump(mode="json", by_alias=False)
    payload = {
        "mode": payload["mode"],
        "display_name": payload["displayName"],
        "visible_properties": payload["visibleProperties"],
        "extended_properties": payload["extendedProperties"],
        "policies": payload["policies"],
    }
    with connect(scope) as conn:
        result, etag = put_overlay(
            conn, scope, installation_pk=installation_pk, target_kind=target_kind,
            target_id=target_id, body=payload, if_match=if_match,
            idempotency_key=idempotency_key, actor=principal.subject,
        )
    response.headers["ETag"] = etag
    return result


@router.get("/v1/ontology/installations/{installation_pk}/overlays")
def get_active_overlays(
    installation_pk: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        items = list_overlays(conn, scope, installation_pk, active_only=True)
    return {"items": items}


@router.get("/v1/ontology/installations/{installation_pk}/overlays/history")
def get_overlay_history(
    installation_pk: str,
    principal: Principal = Depends(require_principal),
) -> dict[str, Any]:
    scope = TenantScope(principal.org_id, principal.project_id)
    with connect(scope) as conn:
        items = list_overlays(conn, scope, installation_pk, active_only=False)
    return {"items": items}
