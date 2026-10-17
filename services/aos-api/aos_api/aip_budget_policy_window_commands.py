"""Exact private-native wire inputs, never approval or runtime admission.

The native Owner resolves the parent, machine maker, checker and paired targets.
No identity supplied in these public values is accepted as that authority.
"""
from datetime import UTC, datetime
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator, AwareDatetime, ConfigDict, Field, StrictInt, StrictStr,
    field_serializer, field_validator, model_validator,
)

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_contracts import AipContractModel


def _canonical_text(value: str) -> str:
    if value != value.strip() or not value.isprintable():
        raise ValueError('canonical printable text required')
    return value


Identity = Annotated[StrictStr, Field(min_length=1, max_length=200), AfterValidator(_canonical_text)]
ModelIdentity = Annotated[StrictStr, Field(min_length=1, max_length=240), AfterValidator(_canonical_text)]
Key = Annotated[StrictStr, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$'), AfterValidator(_canonical_text)]
Hash = Annotated[StrictStr, Field(min_length=64, max_length=64, pattern=r'^[0-9a-f]{64}$')]
PositiveInt = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]


class _ExactRef(VersionedAssetRef):
    model_config = ConfigDict(strict=True)
    asset_id: Identity
    revision: PositiveInt
    content_hash: Hash

    @field_validator('asset_id', 'asset_type', mode='before')
    @classmethod
    def _exact_identity(cls, value):
        # The shared ref's legacy trimming must not silently change wire claims.
        if type(value) is not str or not value:
            raise ValueError('exact reference identity required')
        return _canonical_text(value)


class _WindowCommand(AipContractModel):
    operation: ClassVar[str]
    schema_version: Literal[1]
    org_id: Literal['org-org']
    project_id: Literal['dev-project']
    idempotency_key: Key

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        if type(value) is not int:
            raise ValueError('integer schema version required')
        return value

    def canonical_payload(self) -> dict:
        checked = type(self).model_validate(self.model_dump(mode='python', by_alias=True))
        return checked.model_dump(mode='json', by_alias=True)

    @property
    def request_hash(self) -> str:
        body = self.canonical_payload()
        body.pop('idempotencyKey')
        return canonical_hash({
            'domain': f'aos.budget-policy-window.{self.operation}/v1',
            'command': body,
        })


class WindowProposeCommand(_WindowCommand):
    operation = 'propose'
    parent_cost_proposal_id: Identity
    parent_cost_proposal_hash: Hash
    parent_cost_decision_id: Identity
    parent_consumption_receipt_id: Identity
    expected_budget_ref: _ExactRef
    expected_budget_head_version: PositiveInt
    expected_provider_ref: _ExactRef
    expected_provider_model_id: ModelIdentity
    effective_from: AwareDatetime
    effective_until: AwareDatetime

    @field_validator('expected_budget_ref', 'expected_provider_ref', mode='before')
    @classmethod
    def _ref(cls, value, info):
        if isinstance(value, VersionedAssetRef):
            value = value.model_dump(by_alias=True)
        ref = _ExactRef.model_validate(value)
        expected = 'BudgetRevision' if info.field_name == 'expected_budget_ref' else 'ProviderInstanceRevision'
        if ref.asset_type != expected:
            raise ValueError('wrong parent reference kind')
        return ref

    @field_validator('effective_from', 'effective_until', mode='before')
    @classmethod
    def _timestamp(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError('explicit aware timestamp required')
        return value

    @field_validator('effective_from', 'effective_until')
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_serializer('effective_from', 'effective_until', when_used='json')
    def _wire_time(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec='microseconds').replace('+00:00', 'Z')

    @model_validator(mode='after')
    def _window(self):
        if self.effective_until <= self.effective_from:
            raise ValueError('positive proposed window required')
        # Parent bounds/currentness are Owner facts, not wire shape assertions.
        return self


class WindowDecisionCommand(_WindowCommand):
    operation = 'decide'
    proposal_id: Identity
    proposal_hash: Hash
    target_pair_hash: Hash
    decision: Literal['approved', 'rejected']


class WindowRevocationCommand(_WindowCommand):
    operation = 'revoke'
    proposal_id: Identity
    proposal_hash: Hash
    original_decision_id: Identity
    original_decision_hash: Hash
    reason: Annotated[StrictStr, Field(min_length=1, max_length=500), AfterValidator(_canonical_text)]


class WindowConsumeCommand(_WindowCommand):
    operation = 'consume'
    proposal_id: Identity
    proposal_hash: Hash
    decision_id: Identity
    decision_hash: Hash
    target_pair_hash: Hash
