"""W2-AU · Compute Module Publish 测试（#153 / #154 / #158）.

覆盖 BuildConfigEngine / DockerPublishEngine / ExternalAccessEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.compute_module_publish import (
    # 模型与异常
    BuildConfig,
    BuildConfigEngine,
    BuildConfigError,
    DockerImage,
    DockerPublishEngine,
    DockerPublishError,
    ExternalAccessConfig,
    ExternalAccessEngine,
    ExternalAccessError,
    # getter
    get_build_config_engine,
    get_docker_publish_engine,
    get_external_access_engine,
)


# ════════════════════ BuildConfigEngine ════════════════════

class TestBuildConfig:
    def setup_method(self) -> None:
        self.eng = BuildConfigEngine()
        self.eng._configs = {}

    def test_register_config(self) -> None:
        config = self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0")
        )
        assert config.config_id.startswith("bc-")
        assert config.module_id == "m1"
        assert config.base_image_tag == "0.15.0"
        assert config.status == "active"
        assert config.created_at is not None

    def test_get_config(self) -> None:
        c = self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0")
        )
        fetched = self.eng.get_config(c.config_id)
        assert fetched.config_id == c.config_id
        assert fetched.module_id == "m1"

    def test_get_by_module(self) -> None:
        c = self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0")
        )
        fetched = self.eng.get_by_module("m1")
        assert fetched is not None
        assert fetched.config_id == c.config_id

    def test_list_configs(self) -> None:
        self.eng.register_config(BuildConfig(module_id="m1", base_image_tag="0.15.0"))
        self.eng.register_config(BuildConfig(module_id="m2", base_image_tag="0.15.1"))
        items = self.eng.list_configs()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_config(BuildConfig(module_id="m1", base_image_tag="0.15.0"))
        self.eng.register_config(BuildConfig(module_id="m2", base_image_tag="0.15.1"))
        items = self.eng.list_configs(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_status(self) -> None:
        self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0", status="active")
        )
        self.eng.register_config(
            BuildConfig(module_id="m2", base_image_tag="0.15.1", status="inactive")
        )
        active = self.eng.list_configs(status="active")
        inactive = self.eng.list_configs(status="inactive")
        assert len(active) == 1
        assert active[0].status == "active"
        assert len(inactive) == 1
        assert inactive[0].status == "inactive"

    def test_update_config(self) -> None:
        c = self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0")
        )
        updated = self.eng.update_config(c.config_id, {"status": "inactive"})
        assert updated.status == "inactive"
        assert updated.updated_at is not None

    def test_delete_config(self) -> None:
        c = self.eng.register_config(
            BuildConfig(module_id="m1", base_image_tag="0.15.0")
        )
        self.eng.delete_config(c.config_id)
        with pytest.raises(BuildConfigError) as exc:
            self.eng.get_config(c.config_id)
        assert exc.value.code == "NOT_FOUND"

    def test_validate_base_image_tag_pass(self) -> None:
        assert self.eng.validate_base_image_tag("0.15.0") is True

    def test_validate_base_image_tag_fail(self) -> None:
        assert self.eng.validate_base_image_tag("0.14.9") is False

    def test_validate_base_image_tag_newer(self) -> None:
        assert self.eng.validate_base_image_tag("1.0.0") is True

    def test_missing_module(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.register_config(
                BuildConfig(module_id="", base_image_tag="0.15.0")
            )
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_base_image_tag(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.register_config(
                BuildConfig(module_id="m1", base_image_tag="")
            )
        assert exc.value.code == "MISSING_BASE_IMAGE_TAG"

    def test_invalid_base_image_tag(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.register_config(
                BuildConfig(module_id="m1", base_image_tag="0.14.9")
            )
        assert exc.value.code == "INVALID_BASE_IMAGE_TAG"

    def test_not_found_get(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.get_config("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.update_config("nonexistent", {"status": "inactive"})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        with pytest.raises(BuildConfigError) as exc:
            self.eng.delete_config("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_configs_eviction(self) -> None:
        from aos_api.compute_module_publish import _MAX_BUILD_CONFIGS

        for i in range(_MAX_BUILD_CONFIGS + 5):
            self.eng.register_config(
                BuildConfig(module_id=f"m-{i}", base_image_tag="0.15.0")
            )
        assert len(self.eng._configs) == _MAX_BUILD_CONFIGS


# ════════════════════ DockerPublishEngine ════════════════════

class TestDockerPublish:
    def setup_method(self) -> None:
        self.eng = DockerPublishEngine()
        self.eng._images = {}

    def test_register_image(self) -> None:
        image = self.eng.register_image(
            DockerImage(module_id="m1", tag="v1.0.0")
        )
        assert image.image_id.startswith("di-")
        assert image.module_id == "m1"
        assert image.tag == "v1.0.0"
        assert image.status == "pending"
        assert image.created_at is not None

    def test_get_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0"))
        fetched = self.eng.get_image(img.image_id)
        assert fetched.image_id == img.image_id
        assert fetched.module_id == "m1"

    def test_list_images(self) -> None:
        self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0"))
        self.eng.register_image(DockerImage(module_id="m2", tag="v2.0.0"))
        items = self.eng.list_images()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0"))
        self.eng.register_image(DockerImage(module_id="m2", tag="v2.0.0"))
        items = self.eng.list_images(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_status(self) -> None:
        self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0", status="published"))
        self.eng.register_image(DockerImage(module_id="m2", tag="v2.0.0", status="failed"))
        published = self.eng.list_images(status="published")
        failed = self.eng.list_images(status="failed")
        assert len(published) == 1
        assert published[0].status == "published"
        assert len(failed) == 1
        assert failed[0].status == "failed"

    def test_update_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0"))
        updated = self.eng.update_image(img.image_id, {"tag": "v1.1.0"})
        assert updated.tag == "v1.1.0"
        assert updated.updated_at is not None

    def test_delete_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0"))
        self.eng.delete_image(img.image_id)
        with pytest.raises(DockerPublishError) as exc:
            self.eng.get_image(img.image_id)
        assert exc.value.code == "NOT_FOUND"

    def test_build_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0", status="pending"))
        built = self.eng.build_image(img.image_id)
        assert built.status == "building"

    def test_publish_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0", status="pending"))
        self.eng.build_image(img.image_id)
        published = self.eng.publish_image(img.image_id)
        assert published.status == "published"

    def test_fail_image(self) -> None:
        img = self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0", status="pending"))
        self.eng.build_image(img.image_id)
        failed = self.eng.fail_image(img.image_id, "test error")
        assert failed.status == "failed"

    def test_publish_invalid_latest_tag(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.register_image(DockerImage(module_id="m1", tag="latest"))
        assert exc.value.code == "INVALID_TAG"

    def test_missing_module(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.register_image(DockerImage(module_id="", tag="v1.0.0"))
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_tag(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.register_image(DockerImage(module_id="m1", tag=""))
        assert exc.value.code == "MISSING_TAG"

    def test_invalid_status(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.register_image(DockerImage(module_id="m1", tag="v1.0.0", status="bad"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.get_image("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_build(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.build_image("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_publish(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.publish_image("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_fail(self) -> None:
        with pytest.raises(DockerPublishError) as exc:
            self.eng.fail_image("nonexistent", "not found")
        assert exc.value.code == "NOT_FOUND"

    def test_max_images_eviction(self) -> None:
        from aos_api.compute_module_publish import _MAX_DOCKER_IMAGES

        for i in range(_MAX_DOCKER_IMAGES + 5):
            self.eng.register_image(
                DockerImage(module_id=f"m-{i}", tag=f"v{i}.0.0")
            )
        assert len(self.eng._images) == _MAX_DOCKER_IMAGES


# ════════════════════ ExternalAccessEngine ════════════════════

class TestExternalAccess:
    def setup_method(self) -> None:
        self.eng = ExternalAccessEngine()
        self.eng._configs = {}

    def test_register_config(self) -> None:
        config = self.eng.register_config(
            ExternalAccessConfig(module_id="m1", domain="example.com", access_type="foundry_service", port=443)
        )
        assert config.config_id.startswith("ea-")
        assert config.module_id == "m1"
        assert config.domain == "example.com"
        assert config.access_type == "foundry_service"
        assert config.port == 443
        assert config.status == "active"
        assert config.created_at is not None

    def test_get_config(self) -> None:
        c = self.eng.register_config(
            ExternalAccessConfig(module_id="m1", domain="example.com")
        )
        fetched = self.eng.get_config(c.config_id)
        assert fetched.config_id == c.config_id
        assert fetched.module_id == "m1"

    def test_list_configs(self) -> None:
        self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com"))
        self.eng.register_config(ExternalAccessConfig(module_id="m2", domain="b.com"))
        items = self.eng.list_configs()
        assert len(items) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com"))
        self.eng.register_config(ExternalAccessConfig(module_id="m2", domain="b.com"))
        items = self.eng.list_configs(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_access_type(self) -> None:
        self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com", access_type="foundry_data"))
        self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="b.com", access_type="foundry_service"))
        items = self.eng.list_configs(access_type="foundry_service")
        assert len(items) == 1
        assert items[0].access_type == "foundry_service"

    def test_list_filter_status(self) -> None:
        self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com", status="active"))
        self.eng.register_config(ExternalAccessConfig(module_id="m2", domain="b.com", status="inactive"))
        active = self.eng.list_configs(status="active")
        inactive = self.eng.list_configs(status="inactive")
        assert len(active) == 1
        assert active[0].status == "active"
        assert len(inactive) == 1
        assert inactive[0].status == "inactive"

    def test_update_config(self) -> None:
        c = self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com"))
        updated = self.eng.update_config(c.config_id, {"port": 8080})
        assert updated.port == 8080
        assert updated.updated_at is not None

    def test_delete_config(self) -> None:
        c = self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com"))
        self.eng.delete_config(c.config_id)
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.get_config(c.config_id)
        assert exc.value.code == "NOT_FOUND"

    def test_test_connectivity(self) -> None:
        c = self.eng.register_config(ExternalAccessConfig(module_id="m1", domain="a.com"))
        result = self.eng.test_connectivity(c.config_id)
        assert result["ok"] is True
        assert result["latency_ms"] > 0

    def test_missing_module(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(ExternalAccessConfig(module_id="", domain="a.com"))
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_domain(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(ExternalAccessConfig(module_id="m1", domain=""))
        assert exc.value.code == "MISSING_DOMAIN"

    def test_invalid_access_type(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(
                ExternalAccessConfig(module_id="m1", domain="a.com", access_type="ftp")
            )
        assert exc.value.code == "INVALID_ACCESS_TYPE"

    def test_invalid_port(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(
                ExternalAccessConfig(module_id="m1", domain="a.com", port=0)
            )
        assert exc.value.code == "INVALID_PORT"
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(
                ExternalAccessConfig(module_id="m1", domain="a.com", port=70000)
            )
        assert exc.value.code == "INVALID_PORT"

    def test_invalid_status(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.register_config(
                ExternalAccessConfig(module_id="m1", domain="a.com", status="bad")
            )
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.get_config("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_test_connectivity(self) -> None:
        with pytest.raises(ExternalAccessError) as exc:
            self.eng.test_connectivity("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_max_configs_eviction(self) -> None:
        from aos_api.compute_module_publish import _MAX_ACCESS_CONFIGS

        for i in range(_MAX_ACCESS_CONFIGS + 5):
            self.eng.register_config(
                ExternalAccessConfig(module_id=f"m-{i}", domain=f"{i}.com")
            )
        assert len(self.eng._configs) == _MAX_ACCESS_CONFIGS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_build_config_singleton(self) -> None:
        a = get_build_config_engine()
        b = get_build_config_engine()
        assert a is b

    def test_docker_publish_singleton(self) -> None:
        a = get_docker_publish_engine()
        b = get_docker_publish_engine()
        assert a is b

    def test_external_access_singleton(self) -> None:
        a = get_external_access_engine()
        b = get_external_access_engine()
        assert a is b
