"""W2-AU · Compute Module Publish 引擎（#153 #154 #158）."""
from __future__ import annotations

import random
import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_BUILD_CONFIGS = 200
_MAX_DOCKER_IMAGES = 200
_MAX_ACCESS_CONFIGS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class BuildConfigError(Exception):
    """Build 配置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DockerPublishError(Exception):
    """Docker 镜像发布错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ExternalAccessError(Exception):
    """外部访问配置错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #153 Build Config ════════════════════

class BuildConfig(BaseModel):
    config_id: str = ""
    module_id: str
    base_image_tag: str = "0.15.0"
    dependencies: list[str] = []
    gradle_properties: dict = {}
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_BUILD_STATUSES = {"active", "inactive"}


def _parse_semver(tag: str) -> tuple[int, int, int]:
    """提取 major.minor.patch 并返回数值三元组."""
    parts = tag.lstrip("v").split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch


class BuildConfigEngine:
    """Build 配置引擎（meta.yaml + gradle.properties）."""

    _instance: BuildConfigEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._configs: dict[str, BuildConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> BuildConfigEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_config(self, config: BuildConfig) -> BuildConfig:
        if not config.module_id or not config.module_id.strip():
            raise BuildConfigError("MISSING_MODULE", "module_id is required")
        if not config.base_image_tag or not config.base_image_tag.strip():
            raise BuildConfigError(
                "MISSING_BASE_IMAGE_TAG", "base_image_tag is required")
        if not self.validate_base_image_tag(config.base_image_tag):
            raise BuildConfigError(
                "INVALID_BASE_IMAGE_TAG",
                f"base_image_tag {config.base_image_tag} < minimum 0.15.0")
        if config.status not in _VALID_BUILD_STATUSES:
            raise BuildConfigError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_BUILD_STATUSES}")

        now = _utcnow()
        cid = f"bc-{uuid.uuid4().hex[:8]}"
        stored = config.model_copy(update={
            "config_id": cid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._configs) >= _MAX_BUILD_CONFIGS:
                oldest = min(self._configs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._configs[oldest.config_id]
            self._configs[cid] = stored
        return stored

    def get_config(self, config_id: str) -> BuildConfig:
        with self._lock:
            config = self._configs.get(config_id)
        if config is None:
            raise BuildConfigError(
                "NOT_FOUND", f"config {config_id} not found")
        return config

    def get_by_module(self, module_id: str) -> BuildConfig:
        if not module_id or not module_id.strip():
            raise BuildConfigError("MISSING_MODULE", "module_id is required")
        with self._lock:
            results = [c for c in self._configs.values()
                       if c.module_id == module_id]
        if not results:
            raise BuildConfigError(
                "NOT_FOUND", f"config for module {module_id} not found")
        return sorted(results,
                      key=lambda x: x.created_at or datetime.min,
                      reverse=True)[0]

    def list_configs(
        self,
        module_id: str | None = None,
        status: str | None = None,
    ) -> list[BuildConfig]:
        with self._lock:
            results = list(self._configs.values())
        if module_id:
            results = [c for c in results if c.module_id == module_id]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results,
                      key=lambda c: c.created_at or datetime.min,
                      reverse=True)

    def update_config(self, config_id: str,
                      updates: dict) -> BuildConfig:
        if "status" in updates and updates["status"] not in _VALID_BUILD_STATUSES:
            raise BuildConfigError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_BUILD_STATUSES}")
        if "base_image_tag" in updates:
            if not self.validate_base_image_tag(updates["base_image_tag"]):
                raise BuildConfigError(
                    "INVALID_BASE_IMAGE_TAG",
                    f"base_image_tag {updates['base_image_tag']} < minimum 0.15.0")

        with self._lock:
            config = self._configs.get(config_id)
            if config is None:
                raise BuildConfigError(
                    "NOT_FOUND", f"config {config_id} not found")
            data = config.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = BuildConfig(**data)
            self._configs[config_id] = updated
        return updated

    def delete_config(self, config_id: str) -> None:
        with self._lock:
            if config_id not in self._configs:
                raise BuildConfigError(
                    "NOT_FOUND", f"config {config_id} not found")
            del self._configs[config_id]

    def validate_base_image_tag(self, tag: str) -> bool:
        major, minor, patch = _parse_semver(tag)
        req_major, req_minor, req_patch = _parse_semver("0.15.0")
        if major > req_major:
            return True
        if major == req_major and minor > req_minor:
            return True
        if major == req_major and minor == req_minor and patch >= req_patch:
            return True
        return False


_build_config_engine: BuildConfigEngine | None = None
_build_config_engine_lock = threading.Lock()


def get_build_config_engine() -> BuildConfigEngine:
    global _build_config_engine
    if _build_config_engine is None:
        with _build_config_engine_lock:
            if _build_config_engine is None:
                _build_config_engine = BuildConfigEngine.get_instance()
    return _build_config_engine


# ════════════════════ #154 Docker Publish ════════════════════

class DockerImage(BaseModel):
    image_id: str = ""
    module_id: str
    tag: str
    repository_url: str = ""
    status: str = "pending"  # pending | building | published | failed
    size_bytes: int = 0
    published_at: datetime | None = None
    error_message: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_DOCKER_STATUSES = {"pending", "building", "published", "failed"}


class DockerPublishEngine:
    """Docker 镜像发布引擎."""

    _instance: DockerPublishEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._images: dict[str, DockerImage] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DockerPublishEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_image(self, image: DockerImage) -> DockerImage:
        if not image.module_id or not image.module_id.strip():
            raise DockerPublishError("MISSING_MODULE", "module_id is required")
        if not image.tag or not image.tag.strip():
            raise DockerPublishError("MISSING_TAG", "tag is required")
        if image.tag == "latest":
            raise DockerPublishError(
                "INVALID_TAG", 'tag "latest" is not allowed')
        if image.status not in _VALID_DOCKER_STATUSES:
            raise DockerPublishError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_DOCKER_STATUSES}")

        now = _utcnow()
        iid = f"di-{uuid.uuid4().hex[:8]}"
        stored = image.model_copy(update={
            "image_id": iid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._images) >= _MAX_DOCKER_IMAGES:
                oldest = min(self._images.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._images[oldest.image_id]
            self._images[iid] = stored
        return stored

    def get_image(self, image_id: str) -> DockerImage:
        with self._lock:
            image = self._images.get(image_id)
        if image is None:
            raise DockerPublishError(
                "NOT_FOUND", f"image {image_id} not found")
        return image

    def list_images(
        self,
        module_id: str | None = None,
        status: str | None = None,
    ) -> list[DockerImage]:
        with self._lock:
            results = list(self._images.values())
        if module_id:
            results = [i for i in results if i.module_id == module_id]
        if status:
            results = [i for i in results if i.status == status]
        return sorted(results,
                      key=lambda i: i.created_at or datetime.min,
                      reverse=True)

    def update_image(self, image_id: str,
                     updates: dict) -> DockerImage:
        if "status" in updates and updates["status"] not in _VALID_DOCKER_STATUSES:
            raise DockerPublishError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_DOCKER_STATUSES}")
        if "tag" in updates:
            if updates["tag"] == "latest":
                raise DockerPublishError(
                    "INVALID_TAG", 'tag "latest" is not allowed')

        with self._lock:
            image = self._images.get(image_id)
            if image is None:
                raise DockerPublishError(
                    "NOT_FOUND", f"image {image_id} not found")
            data = image.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = DockerImage(**data)
            self._images[image_id] = updated
        return updated

    def delete_image(self, image_id: str) -> None:
        with self._lock:
            if image_id not in self._images:
                raise DockerPublishError(
                    "NOT_FOUND", f"image {image_id} not found")
            del self._images[image_id]

    def build_image(self, image_id: str) -> DockerImage:
        with self._lock:
            image = self._images.get(image_id)
            if image is None:
                raise DockerPublishError(
                    "NOT_FOUND", f"image {image_id} not found")
            if image.status != "pending":
                raise DockerPublishError(
                    "INVALID_STATUS",
                    f"cannot build from status {image.status}")
            updated = image.model_copy(update={
                "status": "building",
                "updated_at": _utcnow(),
            })
            self._images[image_id] = updated
        return updated

    def publish_image(self, image_id: str) -> DockerImage:
        with self._lock:
            image = self._images.get(image_id)
            if image is None:
                raise DockerPublishError(
                    "NOT_FOUND", f"image {image_id} not found")
            if image.status != "building":
                raise DockerPublishError(
                    "INVALID_STATUS",
                    f"cannot publish from status {image.status}")
            if image.tag == "latest":
                raise DockerPublishError(
                    "INVALID_TAG", 'tag "latest" is not allowed')
            now = _utcnow()
            updated = image.model_copy(update={
                "status": "published",
                "published_at": now,
                "updated_at": now,
            })
            self._images[image_id] = updated
        return updated

    def fail_image(self, image_id: str,
                   error_message: str) -> DockerImage:
        with self._lock:
            image = self._images.get(image_id)
            if image is None:
                raise DockerPublishError(
                    "NOT_FOUND", f"image {image_id} not found")
            if image.status != "building":
                raise DockerPublishError(
                    "INVALID_STATUS",
                    f"cannot fail from status {image.status}")
            updated = image.model_copy(update={
                "status": "failed",
                "error_message": error_message,
                "updated_at": _utcnow(),
            })
            self._images[image_id] = updated
        return updated


_docker_publish_engine: DockerPublishEngine | None = None
_docker_publish_engine_lock = threading.Lock()


def get_docker_publish_engine() -> DockerPublishEngine:
    global _docker_publish_engine
    if _docker_publish_engine is None:
        with _docker_publish_engine_lock:
            if _docker_publish_engine is None:
                _docker_publish_engine = DockerPublishEngine.get_instance()
    return _docker_publish_engine


# ════════════════════ #158 External Access ════════════════════

class ExternalAccessConfig(BaseModel):
    config_id: str = ""
    module_id: str
    access_type: str = "external_domain"  # foundry_data | foundry_service | external_domain
    domain: str
    port: int = 80
    path_prefix: str = ""
    auth_type: str = "none"  # none | bearer | api_key
    auth_config: dict = {}
    status: str = "active"  # active | inactive
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_ACCESS_TYPES = {"foundry_data", "foundry_service", "external_domain"}
_VALID_AUTH_TYPES = {"none", "bearer", "api_key"}
_VALID_ACCESS_STATUSES = {"active", "inactive"}


class ExternalAccessEngine:
    """外部访问配置引擎（Foundry data/services/外部域名）."""

    _instance: ExternalAccessEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._configs: dict[str, ExternalAccessConfig] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ExternalAccessEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register_config(self, config: ExternalAccessConfig) -> ExternalAccessConfig:
        if not config.module_id or not config.module_id.strip():
            raise ExternalAccessError("MISSING_MODULE", "module_id is required")
        if not config.domain or not config.domain.strip():
            raise ExternalAccessError("MISSING_DOMAIN", "domain is required")
        if config.access_type not in _VALID_ACCESS_TYPES:
            raise ExternalAccessError(
                "INVALID_ACCESS_TYPE",
                f"access_type must be one of {_VALID_ACCESS_TYPES}")
        if not (1 <= config.port <= 65535):
            raise ExternalAccessError(
                "INVALID_PORT", "port must be in range 1-65535")
        if config.status not in _VALID_ACCESS_STATUSES:
            raise ExternalAccessError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_ACCESS_STATUSES}")
        if config.auth_type not in _VALID_AUTH_TYPES:
            raise ExternalAccessError(
                "INVALID_AUTH_TYPE",
                f"auth_type must be one of {_VALID_AUTH_TYPES}")

        now = _utcnow()
        cid = f"ea-{uuid.uuid4().hex[:8]}"
        stored = config.model_copy(update={
            "config_id": cid,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock:
            if len(self._configs) >= _MAX_ACCESS_CONFIGS:
                oldest = min(self._configs.values(),
                             key=lambda x: x.created_at or datetime.min)
                del self._configs[oldest.config_id]
            self._configs[cid] = stored
        return stored

    def get_config(self, config_id: str) -> ExternalAccessConfig:
        with self._lock:
            config = self._configs.get(config_id)
        if config is None:
            raise ExternalAccessError(
                "NOT_FOUND", f"config {config_id} not found")
        return config

    def list_configs(
        self,
        module_id: str | None = None,
        access_type: str | None = None,
        status: str | None = None,
    ) -> list[ExternalAccessConfig]:
        with self._lock:
            results = list(self._configs.values())
        if module_id:
            results = [c for c in results if c.module_id == module_id]
        if access_type:
            results = [c for c in results if c.access_type == access_type]
        if status:
            results = [c for c in results if c.status == status]
        return sorted(results,
                      key=lambda c: c.created_at or datetime.min,
                      reverse=True)

    def update_config(self, config_id: str,
                      updates: dict) -> ExternalAccessConfig:
        if "status" in updates and updates["status"] not in _VALID_ACCESS_STATUSES:
            raise ExternalAccessError(
                "INVALID_STATUS",
                f"status must be one of {_VALID_ACCESS_STATUSES}")
        if "access_type" in updates and updates["access_type"] not in _VALID_ACCESS_TYPES:
            raise ExternalAccessError(
                "INVALID_ACCESS_TYPE",
                f"access_type must be one of {_VALID_ACCESS_TYPES}")
        if "port" in updates:
            port = updates["port"]
            if not (1 <= port <= 65535):
                raise ExternalAccessError(
                    "INVALID_PORT", "port must be in range 1-65535")
        if "auth_type" in updates and updates["auth_type"] not in _VALID_AUTH_TYPES:
            raise ExternalAccessError(
                "INVALID_AUTH_TYPE",
                f"auth_type must be one of {_VALID_AUTH_TYPES}")

        with self._lock:
            config = self._configs.get(config_id)
            if config is None:
                raise ExternalAccessError(
                    "NOT_FOUND", f"config {config_id} not found")
            data = config.model_dump()
            data.update(updates)
            data["updated_at"] = _utcnow()
            updated = ExternalAccessConfig(**data)
            self._configs[config_id] = updated
        return updated

    def delete_config(self, config_id: str) -> None:
        with self._lock:
            if config_id not in self._configs:
                raise ExternalAccessError(
                    "NOT_FOUND", f"config {config_id} not found")
            del self._configs[config_id]

    def test_connectivity(self, config_id: str) -> dict:
        config = self.get_config(config_id)
        # 模拟连通性测试
        latency_ms = random.randint(10, 500)
        ok = latency_ms < 300
        return {
            "ok": ok,
            "latency_ms": latency_ms,
            "config_id": config.config_id,
            "domain": config.domain,
            "port": config.port,
        }


_external_access_engine: ExternalAccessEngine | None = None
_external_access_engine_lock = threading.Lock()


def get_external_access_engine() -> ExternalAccessEngine:
    global _external_access_engine
    if _external_access_engine is None:
        with _external_access_engine_lock:
            if _external_access_engine is None:
                _external_access_engine = ExternalAccessEngine.get_instance()
    return _external_access_engine
