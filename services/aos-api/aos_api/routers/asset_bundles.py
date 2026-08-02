"""Canonical asset bundle Registry API — M0/M1 frozen contract §9.1."""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi import Path as ApiPath
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    MAX_BUNDLE_ID_LENGTH,
    BundleKind,
)
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.signature import (
    TRUST_ROOTS_ENV,
    FileTrustRootProvider,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError

router = APIRouter(prefix="/v1/asset-bundles", tags=["asset-registry"])

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_BUNDLE_SOURCE_REF = re.compile(
    rf"^bundle://{BUNDLE_ID_PATTERN.removeprefix('^').removesuffix('$')}/[^/?#%\\]+"
    r"(?:/[^/?#%\\]+)*$"
)

BundleIdPath = Annotated[
    str,
    ApiPath(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    ),
]
VersionPath = Annotated[str, ApiPath(min_length=1, max_length=120)]
PublisherQuery = Annotated[
    str | None,
    Query(min_length=1, max_length=120, pattern=BUNDLE_ID_PATTERN),
]


class StrictRequest(BaseModel):
    """Transport DTOs reject coercion and every field outside the frozen API."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=False,
        validate_assignment=True,
    )


class CreateBundleRequest(StrictRequest):
    publisher: str = Field(
        min_length=1,
        max_length=120,
        pattern=BUNDLE_ID_PATTERN,
    )
    bundle_id: str = Field(
        alias="bundleId",
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    # JSON transports enums as strings; keep every other DTO field strict.
    kind: BundleKind = Field(strict=False)
    display_name: str = Field(alias="displayName", min_length=1, max_length=240)

    @field_validator("display_name")
    @classmethod
    def _normalized_display_name(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise PydanticCustomError(
                "normalized_text",
                "displayName must be normalized",
            )
        return value


class CreateVersionRequest(StrictRequest):
    bundle_source_ref: str = Field(
        alias="bundleSourceRef",
        min_length=1,
        max_length=1024,
    )
    publisher: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=BUNDLE_ID_PATTERN,
    )

    @field_validator("bundle_source_ref")
    @classmethod
    def _allowlisted_source_reference(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise PydanticCustomError(
                "normalized_text",
                "bundleSourceRef must be normalized",
            )
        if _BUNDLE_SOURCE_REF.fullmatch(value) is None:
            raise PydanticCustomError(
                "bundle_source_ref",
                "bundleSourceRef must use bundle://alias/path",
            )
        relative_parts = value.split("/", 3)[3].split("/")
        if any(part in {"", ".", ".."} for part in relative_parts):
            raise PydanticCustomError(
                "bundle_source_ref",
                "bundleSourceRef must not traverse directories",
            )
        return value


class VersionActionRequest(StrictRequest):
    publisher: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=BUNDLE_ID_PATTERN,
    )


class TerminalActionRequest(VersionActionRequest):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _normalized_reason(cls, value: str) -> str:
        if value != value.strip() or "\x00" in value:
            raise PydanticCustomError(
                "normalized_text",
                "reason must be normalized",
            )
        return value


@lru_cache(maxsize=1)
def get_asset_registry_service() -> RegistryService:
    """Build the production service from server-controlled allowlist roots only."""

    allowlist_roots: dict[str, Path] = {}
    catalog_root = _REPOSITORY_ROOT / "bundles"
    if catalog_root.is_dir():
        allowlist_roots["catalog"] = catalog_root

    configured_root = os.getenv("AOS_BUNDLE_ROOT")
    if configured_root:
        allowlist_roots["server"] = Path(configured_root)

    trust_roots = (
        FileTrustRootProvider.from_environment() if os.getenv(TRUST_ROOTS_ENV) else None
    )
    loader = ManifestLoader(allowlist_roots, trust_roots=trust_roots)

    return RegistryService(
        store=PostgresRegistryStore(),
        # Missing or unsafe production trust configuration is deliberately
        # represented by a fail-closed validate/publish gate.
        loader=loader,
        trust_roots=trust_roots,
    )


PrincipalDependency = Annotated[Principal, Depends(require_principal)]
RegistryServiceDependency = Annotated[
    RegistryService,
    Depends(get_asset_registry_service),
]


ResultT = TypeVar("ResultT")


def _invoke(operation: Callable[[], ResultT]) -> ResultT:
    try:
        return operation()
    except AssetRegistryError as exc:
        raise ApiError(
            code=exc.code.value,
            message=str(exc),
            status_code=exc.http_status,
            details=exc.details,
        ) from exc


def _resolve_publisher(
    *,
    query_publisher: str | None,
    body_publisher: str | None,
) -> str | None:
    if (
        query_publisher is not None
        and body_publisher is not None
        and query_publisher != body_publisher
    ):
        raise ApiError(
            code="MANIFEST_INVALID",
            message="publisher query and request body must match",
            status_code=400,
        )
    return query_publisher if query_publisher is not None else body_publisher


@router.get("")
def list_asset_bundles(
    _principal: PrincipalDependency,
    service: RegistryServiceDependency,
) -> list[dict[str, Any]]:
    return _invoke(service.list_bundles)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_asset_bundle(
    request: CreateBundleRequest,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
) -> dict[str, Any]:
    return _invoke(
        lambda: service.create_bundle(
            publisher=request.publisher,
            bundle_id=request.bundle_id,
            kind=request.kind,
            display_name=request.display_name,
            actor=principal.subject,
            roles=principal.roles,
            publisher_scopes=principal.asset_publishers,
        )
    )


@router.get("/{bundle_id}")
def get_asset_bundle(
    bundle_id: BundleIdPath,
    _principal: PrincipalDependency,
    service: RegistryServiceDependency,
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    return _invoke(lambda: service.get_bundle(bundle_id=bundle_id, publisher=publisher))


@router.post("/{bundle_id}/versions", status_code=status.HTTP_201_CREATED)
def create_asset_bundle_version(
    bundle_id: BundleIdPath,
    request: CreateVersionRequest,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    resolved_publisher = _resolve_publisher(
        query_publisher=publisher,
        body_publisher=request.publisher,
    )
    return _invoke(
        lambda: service.create_version(
            bundle_id=bundle_id,
            source_ref=request.bundle_source_ref,
            actor=principal.subject,
            roles=principal.roles,
            publisher=resolved_publisher,
            publisher_scopes=principal.asset_publishers,
        )
    )


@router.get("/{bundle_id}/versions/{version}")
def get_asset_bundle_version(
    bundle_id: BundleIdPath,
    version: VersionPath,
    _principal: PrincipalDependency,
    service: RegistryServiceDependency,
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    return _invoke(
        lambda: service.get_version(
            bundle_id=bundle_id,
            version=version,
            publisher=publisher,
        )
    )


@router.post("/{bundle_id}/versions/{version}/validate")
def validate_asset_bundle_version(
    bundle_id: BundleIdPath,
    version: VersionPath,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
    request: Annotated[VersionActionRequest | None, Body()] = None,
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    resolved_publisher = _resolve_publisher(
        query_publisher=publisher,
        body_publisher=request.publisher if request is not None else None,
    )
    return _invoke(
        lambda: service.validate(
            bundle_id=bundle_id,
            version=version,
            actor=principal.subject,
            roles=principal.roles,
            publisher=resolved_publisher,
            publisher_scopes=principal.asset_publishers,
        )
    )


@router.post("/{bundle_id}/versions/{version}/publish")
def publish_asset_bundle_version(
    bundle_id: BundleIdPath,
    version: VersionPath,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
    request: Annotated[VersionActionRequest | None, Body()] = None,
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    resolved_publisher = _resolve_publisher(
        query_publisher=publisher,
        body_publisher=request.publisher if request is not None else None,
    )
    return _invoke(
        lambda: service.publish(
            bundle_id=bundle_id,
            version=version,
            actor=principal.subject,
            roles=principal.roles,
            publisher=resolved_publisher,
            publisher_scopes=principal.asset_publishers,
        )
    )


@router.post("/{bundle_id}/versions/{version}/deprecate")
def deprecate_asset_bundle_version(
    bundle_id: BundleIdPath,
    version: VersionPath,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
    request: Annotated[TerminalActionRequest, Body()],
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    resolved_publisher = _resolve_publisher(
        query_publisher=publisher,
        body_publisher=request.publisher if request is not None else None,
    )
    return _invoke(
        lambda: service.deprecate(
            bundle_id=bundle_id,
            version=version,
            actor=principal.subject,
            roles=principal.roles,
            reason=request.reason,
            publisher=resolved_publisher,
            publisher_scopes=principal.asset_publishers,
        )
    )


@router.post("/{bundle_id}/versions/{version}/revoke")
def revoke_asset_bundle_version(
    bundle_id: BundleIdPath,
    version: VersionPath,
    principal: PrincipalDependency,
    service: RegistryServiceDependency,
    request: Annotated[TerminalActionRequest, Body()],
    publisher: PublisherQuery = None,
) -> dict[str, Any]:
    resolved_publisher = _resolve_publisher(
        query_publisher=publisher,
        body_publisher=request.publisher if request is not None else None,
    )
    return _invoke(
        lambda: service.revoke(
            bundle_id=bundle_id,
            version=version,
            actor=principal.subject,
            roles=principal.roles,
            reason=request.reason,
            publisher=resolved_publisher,
            publisher_scopes=principal.asset_publishers,
        )
    )
