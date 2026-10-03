"""Strict command input for an isolated BI Plan issuer; no actor authority."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, SecretStr, field_validator

from aos_api.aip_contracts import AipContractModel


_JWT_SHAPE = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}\Z")


class _BIIssuerCommand(AipContractModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    schema_version: Literal[1]
    bearer_token: SecretStr
    org_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    installation_id: str = Field(min_length=36, max_length=36)
    expected_etag_version: int = Field(alias="expectedETagVersion", strict=True, ge=1)
    idempotency_key: str = Field(min_length=1, max_length=120)

    @field_validator("bearer_token")
    @classmethod
    def _jwt_shape(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if len(token) > 8192 or _JWT_SHAPE.fullmatch(token) is None:
            raise ValueError("external OIDC bearer JWT required")
        return value

    @field_validator("org_id", "project_id", "idempotency_key")
    @classmethod
    def _exact_identifier(cls, value: str) -> str:
        if value != value.strip() or not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError("exact printable identifier required")
        return value

    @field_validator("installation_id")
    @classmethod
    def _canonical_installation_id(cls, value: str) -> str:
        try:
            if str(UUID(value)) != value:
                raise ValueError()
        except ValueError:
            raise ValueError("canonical installation UUID required") from None
        return value


class BIIssuerPrepareCommand(_BIIssuerCommand):
    """Prepare a draft from the exact signed installation and ETag."""


class BIIssuerRebindCommand(_BIIssuerCommand):
    """Bind an existing prepared Plan to the current signed installation."""

    plan_id: str = Field(min_length=1, max_length=200)
    prepare_key: str = Field(alias="prepareIdempotencyKey", min_length=1, max_length=120)
    expected_plan_version: int = Field(strict=True, ge=1)

    @field_validator("plan_id", "prepare_key")
    @classmethod
    def _exact_rebind_identifier(cls, value: str) -> str:
        return cls._exact_identifier(value)
