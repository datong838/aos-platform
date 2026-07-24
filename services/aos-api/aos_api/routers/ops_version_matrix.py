"""TWB.6 / CheckIn cleanup — TWB.7 version matrix APIs (ops / air-gap compat)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from aos_api.auth import Principal, require_principal
from aos_api import version_matrix as vm

router = APIRouter(tags=["ops-version-matrix"])


class CheckIn(BaseModel):
    desktop: str | None = None
    spoke: str | None = None
    ferryBundle: str | None = None


@router.get("/v1/ops/version-matrix")
def get_version_matrix(principal: Principal = Depends(require_principal)) -> dict:
    _ = principal
    return vm.get_matrix()


@router.post("/v1/ops/version-matrix/check")
def check_version_matrix(
    body: CheckIn,
    principal: Principal = Depends(require_principal),
) -> dict:
    _ = principal
    return vm.check_versions(
        desktop=body.desktop,
        spoke=body.spoke,
        ferry_bundle=body.ferryBundle,
    )
