"""Exact proposed Owner grant terms, never source or approval authority.

The producer must prove current Owner, provenance, signed policy and installation
in its original tenant transaction before persisting this request as a Proposal.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StrictInt, SecretStr, ValidationError, field_validator, model_validator
from aos_api.aip_action_models import DecideActionProposalRequest

from aos_api.aip_action_store import canonical_hash
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_license_source_action import SOURCE_LICENSE_ISSUANCE_ACTION
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.contracts import SHA256_PATTERN, BUNDLE_ID_PATTERN
from aos_api.asset_registry.semver import parse_version
from aos_api.tenant_scope import TenantScope

_HEX = r'^[0-9a-f]{64}$'


class _SourceCommand(AipContractModel):
    schema_version: Literal[1]
    bearer_token: SecretStr
    org_id: str = Field(min_length=1,max_length=120)
    project_id: str = Field(min_length=1,max_length=120)
    idempotency_key: str = Field(min_length=1,max_length=120)

    @field_validator('schema_version',mode='before')
    @classmethod
    def _version(cls,value):
        if type(value) is not int or value!=1:
            raise ValueError('source command schema version required')
        return value

    @field_validator('bearer_token')
    @classmethod
    def _jwt(cls,value):
        import re
        token=value.get_secret_value()
        if len(token)>8192 or not re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}',token):
            raise ValueError('external signed JWT required')
        return value

    @field_validator('org_id','project_id','idempotency_key',mode='before')
    @classmethod
    def _identifier(cls,value):
        value=_canonical_text(value)
        if any(char.isspace() for char in value):
            raise ValueError('exact source command identifier required')
        return value


def _canonical_text(value: str) -> str:
    if type(value) is not str or not value or value != value.strip() or not value.isprintable():
        raise ValueError('canonical nonempty text required')
    return value


class LicenseEvidenceSourceRef(ExactRevisionRef):
    resource_type: Literal['EvidenceBundleRevision'] = 'EvidenceBundleRevision'
    revision: StrictInt = Field(ge=1)

    @field_validator('resource_id', mode='before')
    @classmethod
    def _exact_id(cls, value):
        return _canonical_text(value)


class SignedLicensePolicyRef(VersionedAssetRef):
    asset_type: Literal['LicensePolicy'] = 'LicensePolicy'
    revision: Literal[1] = 1

    @field_validator('revision', mode='before')
    @classmethod
    def _exact_revision(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('exact policy revision required')
        return value

    @field_validator('asset_id', mode='before')
    @classmethod
    def _exact_id(cls, value):
        return _canonical_text(value)


class SourceLicenseReleaseRef(AipContractModel):
    publisher: str = Field(min_length=1, max_length=160, pattern=BUNDLE_ID_PATTERN)
    bundle_id: str = Field(min_length=1, max_length=160, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(min_length=1, max_length=120)
    content_hash: str = Field(pattern=SHA256_PATTERN)
    signature_fingerprint: str = Field(pattern=SHA256_PATTERN)
    release_evidence_revision: str = Field(pattern=SHA256_PATTERN)

    @field_validator('version')
    @classmethod
    def _version(cls, value):
        _canonical_text(value)
        parse_version(value)
        return value


class SourceLicenseProposalRequest(AipContractModel):
    model_config = ConfigDict(frozen=True)
    source: LicenseEvidenceSourceRef
    source_request_hash: str = Field(pattern=_HEX)
    installation_id: str
    installation_etag: StrictInt = Field(ge=1)
    installation_revision: StrictInt = Field(ge=1)
    release_ref: SourceLicenseReleaseRef
    policy_ref: SignedLicensePolicyRef
    license_id: str = Field(min_length=1, max_length=200)
    usage_purpose: str = Field(min_length=1, max_length=1000)
    permitted_uses: list[Literal['internal_business_analysis', 'traceable_derivation']] = Field(min_length=1, max_length=2)
    rights_attestation: Literal['owner_authorized_for_exact_source_and_uses']
    valid_from: datetime
    valid_until: datetime
    proposal_expires_at: datetime

    @field_validator('installation_id', mode='before')
    @classmethod
    def _installation(cls, value):
        _canonical_text(value)
        if str(UUID(value)) != value:
            raise ValueError('canonical installation UUID required')
        return value

    @field_validator('license_id', 'usage_purpose', mode='before')
    @classmethod
    def _text(cls, value):
        return _canonical_text(value)

    @field_validator('permitted_uses')
    @classmethod
    def _uses(cls, values):
        if len(values) != len(set(values)):
            raise ValueError('unique explicit uses required')
        return sorted(values)

    @field_validator('valid_from', 'valid_until', 'proposal_expires_at')
    @classmethod
    def _utc(cls, value):
        if value.utcoffset() is None:
            raise ValueError('aware grant timestamp required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _window(self):
        if not self.valid_from < self.proposal_expires_at <= self.valid_until:
            raise ValueError('proposal expiry must be within grant window')
        return self


@dataclass(frozen=True, slots=True)
class SourceLicenseRequestBinding:
    content_hash: str
    authorization: Literal['REQUEST_ONLY_NO_START'] = field(default='REQUEST_ONLY_NO_START', init=False)


def source_license_request_binding(scope: TenantScope, maker: str,
                                  request: SourceLicenseProposalRequest) -> SourceLicenseRequestBinding:
    try:
        if type(scope) is not TenantScope or type(request) is not SourceLicenseProposalRequest:
            raise ValueError('exact request and scope required')
        _canonical_text(maker)
        if maker == 'unknown' or any(ch.isspace() for ch in maker):
            raise ValueError('exact actor required')
        # Never trust model_copy/model_construct, including mutated nested refs.
        checked = SourceLicenseProposalRequest.model_validate(request.model_dump(mode='python', by_alias=True))
        payload = {
            'schema': 'aos-source-license-proposal/v1',
            'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
            'maker': maker, 'actionTypeId': SOURCE_LICENSE_ISSUANCE_ACTION,
            'requestedGrant': checked.model_dump(mode='json', by_alias=True),
        }
        return SourceLicenseRequestBinding(canonical_hash(payload))
    except (ValidationError, ValueError, TypeError, AttributeError):
        raise ValueError('SOURCE_LICENSE_REQUEST_INVALID') from None


class SourceLicenseMakerCommand(_SourceCommand):
    request: SourceLicenseProposalRequest


class SourceLicenseApprovalCommand(_SourceCommand):
    proposal_id: str = Field(min_length=1,max_length=160)
    decision: DecideActionProposalRequest

    @field_validator('proposal_id',mode='before')
    @classmethod
    def _proposal_id(cls,value):
        value=_canonical_text(value)
        if any(char.isspace() for char in value):
            raise ValueError('exact proposal identifier required')
        return value
