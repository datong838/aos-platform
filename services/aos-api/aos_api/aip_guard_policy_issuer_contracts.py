"""Strict wire contracts for the isolated Egress/Data/Quota approval issuer."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_guard_policy_issuer import GuardDecisionCommand, _authenticate
from aos_api.aip_runtime_guard_policy_store import canonical_hash


_JWT = re.compile(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}\Z")


class _Base(AipContractModel):
    schema_version: Literal[1]
    bearer_token: SecretStr
    org_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    proposal_id: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=120)
    decision: DecideActionProposalRequest

    @field_validator("bearer_token")
    @classmethod
    def _bearer(cls, value):
        raw = value.get_secret_value()
        if len(raw) > 8192 or _JWT.fullmatch(raw) is None:
            raise ValueError("external OIDC bearer JWT required")
        return value

    @field_validator("org_id", "project_id", "proposal_id", "idempotency_key")
    @classmethod
    def _identifier(cls, value):
        if value != value.strip() or not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError("exact printable identifier required")
        return value

    @property
    def request_hash(self):
        return canonical_hash(self.decision.model_dump(mode="json", by_alias=True))

    def command(self):
        return GuardDecisionCommand(orgId=self.org_id, projectId=self.project_id,
            bearerToken=self.bearer_token, proposalId=self.proposal_id,
            idempotencyKey=self.idempotency_key, decision=self.decision)


class GuardIssuerDecisionCommand(_Base):
    def inquiry(self):
        return GuardIssuerDecisionInquiry(**self.model_dump(), requestHash=self.request_hash)


class GuardIssuerDecisionInquiry(_Base):
    request_hash_value: str = Field(alias="requestHash", pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bound(self):
        if self.request_hash_value != self.request_hash:
            raise ValueError("original decision hash required")
        return self

    def matches(self, command):
        return type(command) is GuardIssuerDecisionCommand and self.model_dump(exclude={"request_hash_value"}) == command.model_dump()


def authenticate_guard_issuer_request(request):
    if type(request) not in (GuardIssuerDecisionCommand, GuardIssuerDecisionInquiry):
        raise ValueError("exact guard issuer request required")
    _command, principal, _scope = _authenticate(request.command(), GuardDecisionCommand)
    return principal
