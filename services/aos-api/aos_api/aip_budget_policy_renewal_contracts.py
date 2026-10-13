"""Actor-free public inputs for the separately authenticated renewal boundary.

Parsing these commands proves neither current Owner facts nor identity, approval,
publication or execution permission. The store must establish those separately.
"""
from datetime import UTC, datetime
import re
from typing import Annotated, ClassVar, Literal

from pydantic import AwareDatetime, ConfigDict, Field, StrictInt, StrictStr
from pydantic import field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_model_governance_policy_store import canonical_hash


ExactVersion = Annotated[StrictInt, Field(ge=1, le=9_007_199_254_740_991)]
ExactHash = Annotated[StrictStr, Field(pattern=r'^[0-9a-f]{64}$')]
Identifier = Annotated[StrictStr, Field(
    min_length=1, max_length=160, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')]
PolicyIdentifier = Annotated[StrictStr, Field(
    min_length=1, max_length=200, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')]
_ISO_WINDOW = re.compile(
    r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
    r'(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})$'
)


class _RenewalCommand(AipContractModel):
    model_config = ConfigDict(frozen=True)
    domain: ClassVar[str]
    schema_version: Literal[1]
    org_id: Literal['org-org']
    project_id: Literal['dev-project']
    idempotency_key: Annotated[StrictStr, Field(
        min_length=1, max_length=120, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')]

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        if type(value) is not int:
            raise ValueError('exact integer schema version required')
        return value

    @property
    def activation_eligible(self) -> Literal[False]:
        return False

    def canonical_payload(self) -> dict:
        # model_copy can bypass validators, so every usable hash reparses fields.
        checked = type(self).model_validate(self.model_dump(mode='python', by_alias=True))
        return checked.model_dump(mode='json', by_alias=True)

    @property
    def request_hash(self) -> str:
        value = self.canonical_payload()
        value.pop('idempotencyKey')
        # The authenticated actor and original key belong to the Owner's receipt
        # namespace; this hash binds the operation's nonsecret semantic input.
        return canonical_hash({'domain': self.domain, 'command': value})


class RenewalProposalCommand(_RenewalCommand):
    """Condition a machine proposal on a source head, never supply a target body."""
    domain = 'aos.budget-policy-renewal.propose/v1'
    source_policy_id: PolicyIdentifier
    expected_source_revision: ExactVersion
    expected_head_version: ExactVersion
    expected_source_hash: ExactHash
    effective_from: AwareDatetime
    effective_until: AwareDatetime

    @field_validator('effective_from', 'effective_until', mode='before')
    @classmethod
    def _explicit_window(cls, value):
        if type(value) is datetime:
            return value
        if type(value) is not str or _ISO_WINDOW.fullmatch(value) is None:
            raise ValueError('explicit ISO timestamp with timezone required')
        return value

    @field_validator('effective_from', 'effective_until')
    @classmethod
    def _utc_window(cls, value):
        return value.astimezone(UTC)

    @model_validator(mode='after')
    def _ordered_window(self):
        if self.effective_until <= self.effective_from:
            raise ValueError('renewal window must be nonempty and ordered')
        # Current time, original Budget bounds and the historical policy window
        # require locked Owner facts, not this pure request parser.
        return self


class RenewalDecisionCommand(_RenewalCommand):
    """Decide the exact prepared target; identity comes from the private issuer."""
    domain = 'aos.budget-policy-renewal.decide/v1'
    proposal_id: Identifier
    proposal_hash: ExactHash
    target_active_hash: ExactHash
    decision: Literal['approved', 'rejected']


class RenewalConsumeCommand(_RenewalCommand):
    """Identify an original decision for consumption or read-only reconciliation."""
    domain = 'aos.budget-policy-renewal.consume/v1'
    proposal_id: Identifier
    proposal_hash: ExactHash
    decision_id: Identifier
    decision_hash: ExactHash


class RenewalRevocationCommand(RenewalConsumeCommand):
    """Withdraw one exact decision through the independently authenticated issuer.

    This input is neither a persisted revocation nor evidence of human consent.
    The issuer must serialize withdrawal with consumption at the proposal lock.
    """
    domain = 'aos.budget-policy-renewal.revoke/v1'
    reason_code: Literal['approval_withdrawn', 'scope_changed', 'dependency_changed']
