"""W2-AU · Compute Module Publish 路由（#153 #154 #158）."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.auth import require_principal
from aos_api.compute_module_publish import (
    BuildConfig,
    BuildConfigError,
    DockerImage,
    DockerPublishError,
    ExternalAccessConfig,
    ExternalAccessError,
    get_build_config_engine,
    get_docker_publish_engine,
    get_external_access_engine,
)
from aos_api.errors import ApiError

router = APIRouter(
    prefix="/compute-module-publish", tags=["Compute Module Publish"])


def _map_build_err(e: BuildConfigError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_BASE_IMAGE_TAG": (400, "缺少 base_image_tag"),
        "INVALID_BASE_IMAGE_TAG": (400, "base_image_tag 无效（须 >= 0.15.0）"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_docker_err(e: DockerPublishError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_TAG": (400, "缺少 tag"),
        "INVALID_TAG": (400, 'tag 不能为 "latest"'),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


def _map_access_err(e: ExternalAccessError) -> HTTPException:
    mapping = {
        "MISSING_MODULE": (400, "缺少 module_id"),
        "MISSING_DOMAIN": (400, "缺少 domain"),
        "INVALID_ACCESS_TYPE": (400, "access_type 无效"),
        "INVALID_PORT": (400, "port 必须在 1-65535 之间"),
        "INVALID_STATUS": (400, "状态无效"),
        "NOT_FOUND": (404, "资源不存在"),
    }
    status, msg = mapping.get(e.code, (400, e.message))
    return HTTPException(
        status_code=status,
        detail=ApiError(code=e.code, message=msg).model_dump(),
    )


# ════════════════════ #153 Build Config ════════════════════
# 注意：字面量路由 /build-configs/module/{module_id} 和 /build-configs/validate-tag
# 须注册在参数路由 /build-configs/{config_id} 之前。

@router.post("/build-configs", response_model=BuildConfig)
def register_build_config(body: BuildConfig, _=require_principal):
    try:
        return get_build_config_engine().register_config(body)
    except BuildConfigError as e:
        raise _map_build_err(e) from e


@router.get("/build-configs/module/{module_id}", response_model=BuildConfig)
def get_build_config_by_module(module_id: str, _=require_principal):
    try:
        return get_build_config_engine().get_by_module(module_id)
    except BuildConfigError as e:
        raise _map_build_err(e) from e


@router.get("/build-configs/{config_id}", response_model=BuildConfig)
def get_build_config(config_id: str, _=require_principal):
    try:
        return get_build_config_engine().get_config(config_id)
    except BuildConfigError as e:
        raise _map_build_err(e) from e


@router.get("/build-configs", response_model=list[BuildConfig])
def list_build_configs(
    module_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_build_config_engine().list_configs(
        module_id=module_id, status=status)


@router.put("/build-configs/{config_id}", response_model=BuildConfig)
def update_build_config(config_id: str, updates: dict, _=require_principal):
    try:
        return get_build_config_engine().update_config(config_id, updates)
    except BuildConfigError as e:
        raise _map_build_err(e) from e


@router.delete("/build-configs/{config_id}")
def delete_build_config(config_id: str, _=require_principal):
    try:
        get_build_config_engine().delete_config(config_id)
        return {"deleted": True}
    except BuildConfigError as e:
        raise _map_build_err(e) from e


class ValidateTagBody(BaseModel):
    tag: str


@router.post("/build-configs/validate-tag")
def validate_build_tag(body: ValidateTagBody, _=require_principal):
    ok = get_build_config_engine().validate_base_image_tag(body.tag)
    return {"valid": ok, "tag": body.tag}


# ════════════════════ #154 Docker Publish ════════════════════

@router.post("/docker-images", response_model=DockerImage)
def register_docker_image(body: DockerImage, _=require_principal):
    try:
        return get_docker_publish_engine().register_image(body)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


@router.get("/docker-images/{image_id}", response_model=DockerImage)
def get_docker_image(image_id: str, _=require_principal):
    try:
        return get_docker_publish_engine().get_image(image_id)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


@router.get("/docker-images", response_model=list[DockerImage])
def list_docker_images(
    module_id: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_docker_publish_engine().list_images(
        module_id=module_id, status=status)


@router.put("/docker-images/{image_id}", response_model=DockerImage)
def update_docker_image(image_id: str, updates: dict, _=require_principal):
    try:
        return get_docker_publish_engine().update_image(image_id, updates)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


@router.delete("/docker-images/{image_id}")
def delete_docker_image(image_id: str, _=require_principal):
    try:
        get_docker_publish_engine().delete_image(image_id)
        return {"deleted": True}
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


@router.post("/docker-images/{image_id}/build", response_model=DockerImage)
def build_docker_image(image_id: str, _=require_principal):
    try:
        return get_docker_publish_engine().build_image(image_id)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


@router.post("/docker-images/{image_id}/publish", response_model=DockerImage)
def publish_docker_image(image_id: str, _=require_principal):
    try:
        return get_docker_publish_engine().publish_image(image_id)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


class FailImageBody(BaseModel):
    error_message: str


@router.post("/docker-images/{image_id}/fail", response_model=DockerImage)
def fail_docker_image(image_id: str, body: FailImageBody, _=require_principal):
    try:
        return get_docker_publish_engine().fail_image(
            image_id, body.error_message)
    except DockerPublishError as e:
        raise _map_docker_err(e) from e


# ════════════════════ #158 External Access ════════════════════

@router.post("/access-configs", response_model=ExternalAccessConfig)
def register_access_config(body: ExternalAccessConfig, _=require_principal):
    try:
        return get_external_access_engine().register_config(body)
    except ExternalAccessError as e:
        raise _map_access_err(e) from e


@router.get("/access-configs/{config_id}", response_model=ExternalAccessConfig)
def get_access_config(config_id: str, _=require_principal):
    try:
        return get_external_access_engine().get_config(config_id)
    except ExternalAccessError as e:
        raise _map_access_err(e) from e


@router.get("/access-configs", response_model=list[ExternalAccessConfig])
def list_access_configs(
    module_id: str | None = Query(None),
    access_type: str | None = Query(None),
    status: str | None = Query(None),
    _=require_principal,
):
    return get_external_access_engine().list_configs(
        module_id=module_id, access_type=access_type, status=status)


@router.put("/access-configs/{config_id}", response_model=ExternalAccessConfig)
def update_access_config(config_id: str, updates: dict, _=require_principal):
    try:
        return get_external_access_engine().update_config(config_id, updates)
    except ExternalAccessError as e:
        raise _map_access_err(e) from e


@router.delete("/access-configs/{config_id}")
def delete_access_config(config_id: str, _=require_principal):
    try:
        get_external_access_engine().delete_config(config_id)
        return {"deleted": True}
    except ExternalAccessError as e:
        raise _map_access_err(e) from e


@router.post("/access-configs/{config_id}/test-connectivity")
def test_access_connectivity(config_id: str, _=require_principal):
    try:
        return get_external_access_engine().test_connectivity(config_id)
    except ExternalAccessError as e:
        raise _map_access_err(e) from e
