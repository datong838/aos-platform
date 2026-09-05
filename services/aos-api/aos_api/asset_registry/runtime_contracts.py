"""Signed runtime declarations only; no imports or execution of bundle code."""

from __future__ import annotations

import keyword
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RuntimeContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


def _path(value: str, root: str, suffix: str) -> str:
    if (not value.startswith(root + "/") or not value.endswith(suffix)
            or any(c in value for c in "\\%?#:~")
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("runtime path must be an exact bundle-relative path")
    return value


class BackendRuntime(RuntimeContract):
    entrypoint: str = Field(min_length=1, max_length=1024)
    python_package: str = Field(alias="pythonPackage", min_length=1, max_length=160)
    schema_namespace: str = Field(alias="schemaNamespace", min_length=1, max_length=63,
                                  pattern=r"^[a-z][a-z0-9_]*$")
    profile_id: Literal["internal-python-v1"] = Field(alias="profileId")
    image_index: str = Field(alias="imageIndex", min_length=1, max_length=1024)

    @field_validator("entrypoint")
    @classmethod
    def check_entrypoint(cls, value: str) -> str:
        if not value.endswith(":register"):
            raise ValueError("only register is supported")
        _path(value.removesuffix(":register"), "backend", ".py")
        return value

    @field_validator("python_package")
    @classmethod
    def check_package(cls, value: str) -> str:
        if any(not p.isidentifier() or keyword.iskeyword(p) for p in value.split(".")):
            raise ValueError("invalid Python package")
        return value

    @field_validator("schema_namespace")
    @classmethod
    def check_namespace(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("invalid schema namespace")
        return value

    @field_validator("image_index")
    @classmethod
    def check_index(cls, value: str) -> str:
        return _path(value, "artifacts", ".json")


class FrontendRuntime(RuntimeContract):
    manifest: str = Field(min_length=1, max_length=1024)
    artifact_hash: str = Field(alias="artifactHash", min_length=71, max_length=71,
                               pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("manifest")
    @classmethod
    def check_manifest(cls, value: str) -> str:
        return _path(value, "frontend", ".json")


class RuntimeSpec(RuntimeContract):
    api_version: Literal["aos.dev/bundle-runtime/v1alpha1"] = Field(alias="apiVersion")
    backend: BackendRuntime | None = Field(default=None, exclude_if=lambda v: v is None)
    frontend: FrontendRuntime | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def nonempty(self) -> RuntimeSpec:
        if self.backend is None and self.frontend is None:
            raise ValueError("runtime requires backend or frontend")
        return self
