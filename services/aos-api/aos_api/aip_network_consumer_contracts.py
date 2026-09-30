"""Strict no-effect commands for the independent network consumer service."""
from __future__ import annotations
import re
from typing import Literal
from pydantic import ConfigDict, Field, SecretStr, field_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_action_store import canonical_hash


class _ConsumerRequest(AipContractModel):
    model_config = ConfigDict(strict=True, frozen=True)
    schema_version: Literal[1]
    bearer_token: SecretStr
    org_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    proposal_id: str = Field(min_length=1, max_length=160)
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    approval_event_id: str = Field(min_length=1, max_length=160)
    target_content_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    binding_hash: str = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('exact schema version required')
        return value

    @field_validator('bearer_token')
    @classmethod
    def _jwt_shape(cls, value: SecretStr):
        token = value.get_secret_value()
        if len(token) > 8192 or re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}', token) is None:
            raise ValueError('external OIDC bearer JWT required')
        return value

    @field_validator('org_id', 'project_id', 'proposal_id', 'approval_event_id')
    @classmethod
    def _identifier(cls, value):
        if not value.isprintable() or any(ch.isspace() for ch in value):
            raise ValueError('exact printable identifier required')
        return value

    @property
    def idempotency_key(self):
        return self.proposal_id

    @property
    def request_hash(self):
        return canonical_hash(self.model_dump(mode='json', by_alias=True, exclude={'bearer_token'}))


class NetworkConsumerCommand(_ConsumerRequest):
    def inquiry(self) -> NetworkConsumerInquiry:
        return NetworkConsumerInquiry.model_validate(self.model_dump())


class NetworkConsumerInquiry(_ConsumerRequest):
    def matches(self, command: NetworkConsumerCommand) -> bool:
        return type(command) is NetworkConsumerCommand and self.request_hash == command.request_hash
