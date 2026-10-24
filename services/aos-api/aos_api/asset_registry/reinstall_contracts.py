"""Pure reinstall command payloads; no lifecycle, authorization or execution."""
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from aos_api.asset_registry.composition_contracts import (
    CreateInstallationRequest,
    _canonical_uuid,
)
from aos_api.asset_registry.contracts import SHA256_PATTERN, StrictContract


class ReinstallSourceRef(StrictContract):
    """Exact terminal source reference; the server must verify current authority."""

    model_config = ConfigDict(revalidate_instances="always")

    installation_id: str = Field(alias="installationId")
    terminal_revision: int = Field(alias="terminalRevision", ge=1)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)

    @field_validator("installation_id")
    @classmethod
    def _source_uuid(cls, value: str) -> str:
        return _canonical_uuid(value, label="source installationId")


class ReinstallInstallationRequest(StrictContract):
    """Independent new command; never add these fields to legacy create payloads."""

    model_config = ConfigDict(revalidate_instances="always")

    source: ReinstallSourceRef
    target: CreateInstallationRequest

    @field_validator("source", mode="before")
    @classmethod
    def _recheck_source(cls, value: Any) -> Any:
        if type(value) is ReinstallSourceRef:
            return value.model_dump(mode="python", by_alias=True)
        if type(value) is dict:
            return value
        raise ValueError("source must be an exact source reference or JSON object")

    @field_validator("target", mode="before")
    @classmethod
    def _recheck_target(cls, value: Any) -> Any:
        if type(value) is CreateInstallationRequest:
            return value.model_dump(mode="python", by_alias=True)
        if type(value) is dict:
            return value
        raise ValueError("target must be an exact legacy create request or JSON object")
