"""Strict, no-effect contracts for an isolated network approval issuer."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_action_store import canonical_hash
from aos_api.aip_contracts import AipContractModel


_JWT_SHAPE = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}\Z")


class _IssuerRequestBase(AipContractModel):
    schema_version: Literal[1]
    bearer_token: SecretStr
    org_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    proposal_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=120)

    @field_validator("bearer_token")
    @classmethod
    def _jwt_shape(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if len(token) > 8192 or _JWT_SHAPE.fullmatch(token) is None:
            raise ValueError("external OIDC bearer JWT required")
        return value

    @field_validator("org_id", "project_id", "proposal_id", "idempotency_key")
    @classmethod
    def _exact_identifier(cls, value: str) -> str:
        if value != value.strip() or not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError("exact printable identifier required")
        return value


class NetworkIssuerDecisionCommand(_IssuerRequestBase):
    decision: DecideActionProposalRequest

    @property
    def request_hash(self) -> str:
        return canonical_hash(self.decision.model_dump(mode="json", by_alias=True))

    def inquiry(self) -> "NetworkIssuerDecisionInquiry":
        return NetworkIssuerDecisionInquiry(
            schema_version=1, bearer_token=self.bearer_token,
            org_id=self.org_id, project_id=self.project_id,
            proposal_id=self.proposal_id, idempotency_key=self.idempotency_key,
            request_hash=self.request_hash,
        )


class NetworkIssuerDecisionInquiry(_IssuerRequestBase):
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def matches(self, command: NetworkIssuerDecisionCommand) -> bool:
        return (self.schema_version == command.schema_version
                and self.org_id == command.org_id
                and self.project_id == command.project_id
                and self.proposal_id == command.proposal_id
                and self.idempotency_key == command.idempotency_key
                and self.request_hash == command.request_hash)
