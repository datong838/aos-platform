"""Immutable pipeline control drafts; parsing never grants execution authority."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.asset_registry.contracts import BUNDLE_ID_PATTERN, SHA256_PATTERN
from aos_api.asset_registry.semver import parse_version
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef
from aos_api.tenant_scope import TenantScope

_MAX_REVISION = 2**63 - 1
_FROZEN = ConfigDict(strict=True, frozen=True, extra='forbid',
                     revalidate_instances='always', hide_input_in_errors=True)


def _canonical_uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError('canonical UUID required')
    return value


def _canonical_text(value):
    if isinstance(value, str) and (not value or value != value.strip() or not value.isprintable()):
        raise ValueError('canonical nonempty identity required')
    return value


class PipelineInstallationRef(CurrentInstallationRef):
    # Instance revalidation supplies field names, while wire input uses aliases.
    model_config = ConfigDict(**_FROZEN, validate_by_name=True)


class PipelineExactRef(InvestigationExactRef):
    model_config = _FROZEN

    @field_validator('resource_type', 'resource_id', 'revision', mode='before')
    @classmethod
    def canonical_identity(cls, value):
        return _canonical_text(value)

    @model_validator(mode='after')
    def no_receipt_shortcut(self):
        if self.receipt_id is not None:
            raise ValueError('a pinned reference cannot substitute a receipt')
        if type(self.revision) is int and self.revision > _MAX_REVISION:
            raise ValueError('revision exceeds storage range')
        return self


class PipelinePackageRef(AipContractModel):
    model_config = _FROZEN
    publisher: str = Field(min_length=1, max_length=160, pattern=BUNDLE_ID_PATTERN)
    id: str = Field(min_length=1, max_length=160, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(min_length=1, max_length=160)
    content_hash: str = Field(pattern=SHA256_PATTERN)

    @field_validator('version')
    @classmethod
    def exact_version(cls, value):
        _canonical_text(value)
        parse_version(value)
        return value


class PipelineRuntimeControlDraft(AipContractModel):
    """All refs must still be resolved by current locked Owners before any use."""
    model_config = _FROZEN
    schema_version: Literal['aos.pipeline-runtime-control-draft/v1'] = 'aos.pipeline-runtime-control-draft/v1'
    state: Literal['prepared'] = 'prepared'
    read_only: Literal[True] = True
    org_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    pipeline_id: str = Field(min_length=1, max_length=200)
    graph_revision: int = Field(ge=1, le=_MAX_REVISION)
    graph_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    installation_ref: PipelineInstallationRef
    generation: str
    execution_epoch: int = Field(ge=1, le=_MAX_REVISION)
    configuration_ref: ConfigurationRef
    package_ref: PipelinePackageRef
    source_id: str = Field(min_length=1, max_length=200)
    source_configuration_ref: PipelineExactRef
    source_selection_ref: PipelineExactRef
    mapping_ref: PipelineExactRef
    schema_ref: PipelineExactRef
    masking_policy_ref: PipelineExactRef
    row_limit: int = Field(ge=1, le=1000)
    timeout_seconds: int = Field(ge=1, le=30)
    max_source_calls: int = Field(ge=1, le=32)
    not_before: datetime
    expires_at: datetime

    @field_validator('read_only', mode='before')
    @classmethod
    def readonly_only(cls, value):
        if type(value) is not bool or value is not True:
            raise ValueError('explicit read-only mode required')
        return value

    @field_validator('org_id', 'project_id', 'pipeline_id', 'source_id')
    @classmethod
    def canonical_identity(cls, value):
        return _canonical_text(value)

    @field_validator('generation')
    @classmethod
    def canonical_generation(cls, value):
        return _canonical_uuid(value)

    @field_validator('not_before', 'expires_at')
    @classmethod
    def aware_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError('timezone required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def exact_bounds(self):
        TenantScope(self.org_id, self.project_id)
        expected = (
            (self.source_configuration_ref, 'DataSourceConfigurationRevision'),
            (self.source_selection_ref, 'SourceSelectionRevision'),
            (self.mapping_ref, 'Mapping'),
            (self.schema_ref, 'SchemaFingerprint'),
            (self.masking_policy_ref, 'MaskingPolicy'),
        )
        if any(ref.resource_type != kind for ref, kind in expected):
            raise ValueError('reference purpose differs')
        source = self.source_configuration_ref
        if not source.resource_id.startswith('source-config-') or type(source.revision) is not int or source.revision != 1:
            raise ValueError('exact source configuration revision required')
        _canonical_uuid(source.resource_id.removeprefix('source-config-'))
        if type(self.source_selection_ref.revision) is not int:
            raise ValueError('integer source selection revision required')
        if self.installation_ref.revision > _MAX_REVISION:
            raise ValueError('installation revision exceeds storage range')
        duration = self.expires_at - self.not_before
        if not timedelta(0) < duration <= timedelta(days=1):
            raise ValueError('control window must be positive and at most 24 hours')
        return self

    def content_hash(self) -> str:
        validated = type(self).model_validate(self)
        return canonical_sha256(validated.model_dump(mode='json', by_alias=True))
