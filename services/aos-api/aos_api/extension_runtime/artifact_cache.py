"""Resolve signed image-index bytes against the local immutable image cache."""
import hashlib
import json
from typing import Literal

from pydantic import Field, field_validator

from aos_api.asset_registry.runtime_contracts import RuntimeContract, _path
from aos_api.extension_runtime.ipc import _pairs


class ImageArtifact(RuntimeContract):
    platform: Literal["linux/arm64", "linux/amd64"]
    image_digest: str = Field(alias="imageDigest", pattern=r"^sha256:[0-9a-f]{64}$", min_length=71, max_length=71)
    config_digest: str = Field(alias="configDigest", pattern=r"^sha256:[0-9a-f]{64}$", min_length=71, max_length=71)
    dependency_lock_hash: str = Field(alias="dependencyLockHash", pattern=r"^sha256:[0-9a-f]{64}$", min_length=71, max_length=71)
    sbom_path: str = Field(alias="sbomPath", min_length=1, max_length=1024)

    @field_validator("sbom_path")
    @classmethod
    def safe_sbom(cls, value):
        return _path(value, "evidence", ".json")


class ImageIndex(RuntimeContract):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    images: list[ImageArtifact] = Field(min_length=1, max_length=2)


def resolve_image_index(raw: bytes, *, expected_hash: str, platform: str) -> ImageArtifact:
    """Caller supplies hash from the verified signed bundle artifact list."""
    if len(raw) > 65536 or "sha256:" + hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("image index digest or size mismatch")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    if type(value) is not dict or type(value.get("schemaVersion")) is not int:
        raise ValueError("invalid image index version")
    index = ImageIndex.model_validate(value)
    if len({item.platform for item in index.images}) != len(index.images):
        raise ValueError("duplicate image platform")
    for item in index.images:
        if item.platform == platform:
            return item
    raise ValueError("no approved image for this architecture")


def require_cached_image(driver, artifact: ImageArtifact) -> str:
    """No download fallback: registry digest and configuration must both agree."""
    rows = json.loads(driver._run("image", "inspect", artifact.config_digest))
    if len(rows) != 1:
        raise ValueError("image cache mismatch")
    row = rows[0]
    digests = [ref.rsplit("@", 1)[-1] for ref in row.get("RepoDigests", [])]
    if row.get("Id") != artifact.config_digest or artifact.image_digest not in digests:
        raise ValueError("cached artifact differs from signed image index")
    if row.get("Os", "") + "/" + row.get("Architecture", "") != artifact.platform:
        raise ValueError("cached image architecture mismatch")
    return artifact.config_digest
