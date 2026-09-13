"""Pinned product-event policy input, never admission or source-read authority."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.configuration_contracts import ConfigurationRef
from aos_api.pipeline_runtime_control_contracts import (
    PipelineExactRef, PipelineInstallationRef, PipelineSourceSelectionDraft,
)
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.tenant_scope import TenantScope


class ProductEventPolicyDraft(AipContractModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid',
        revalidate_instances='always', hide_input_in_errors=True)
    schema_version: Literal['aos.product-event-policy-draft/v1'] = 'aos.product-event-policy-draft/v1'
    policy_id: str = Field(min_length=1, max_length=200)
    org_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    installation_ref: PipelineInstallationRef
    generation: str
    execution_epoch: int = Field(ge=1, le=2**63-1)
    configuration_ref: ConfigurationRef
    source_selection_ref: PipelineExactRef
    source_configuration_ref: PipelineExactRef
    platform: str = Field(min_length=1, max_length=160)
    shop_or_marketplace_id: str = Field(min_length=1, max_length=200)
    object_types: tuple[Literal['Product', 'ProductSku'], ...] = Field(min_length=1, max_length=2)
    method_version: Literal['aos.product-source-event/v1']
    effective_from: datetime
    effective_until: datetime
    max_source_age_seconds: int = Field(ge=1, le=86400)
    recovery_window_seconds: int = Field(ge=1, le=86400)

    @field_validator('policy_id', 'org_id', 'project_id', 'platform', 'shop_or_marketplace_id')
    @classmethod
    def canonical_text(cls, value):
        if value != value.strip() or not value.isprintable():
            raise ValueError('canonical identity required')
        return value

    @field_validator('generation')
    @classmethod
    def canonical_generation(cls, value):
        if str(UUID(value)) != value:
            raise ValueError('canonical generation required')
        return value

    @field_validator('effective_from', 'effective_until')
    @classmethod
    def aware_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError('timezone required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def bounded(self):
        TenantScope(self.org_id, self.project_id)
        if not timedelta(0) < self.effective_until-self.effective_from <= timedelta(days=1):
            raise ValueError('event policy window must be positive and at most one day')
        if len(set(self.object_types)) != len(self.object_types):
            raise ValueError('duplicate event object type')
        for ref, kind in ((self.source_selection_ref, 'SourceSelectionRevision'),
                          (self.source_configuration_ref, 'DataSourceConfigurationRevision')):
            if ref.resource_type != kind or type(ref.revision) is not int:
                raise ValueError('exact source reference purpose differs')
        return self

    def content_hash(self) -> str:
        checked = type(self).model_validate(self)
        return canonical_sha256(checked.model_dump(mode='json', by_alias=True))

    def validate_selection(self, record: SourceSelectionRecord) -> None:
        """Check correlation only; the caller must authenticate and re-read the Owner."""
        checked = type(self).model_validate(self)
        if type(record) is not SourceSelectionRecord:
            raise ValueError('exact source selection record required')
        source = PipelineSourceSelectionDraft.model_validate(record.draft)
        spec = record.read_spec
        if type(spec) is not MappingReadSpec:
            raise ValueError('exact mapping specification required')
        MappingReadSpec(spec.table, spec.object_type, spec.primary_key, spec.columns, spec.filters)
        if checked.object_types != (spec.object_type,):
            raise ValueError('event objects exceed the selected mapping')
        if PipelineExactRef.model_validate(record.ref) != checked.source_selection_ref:
            raise ValueError('source selection reference differs')
        for name in ('org_id', 'project_id', 'installation_ref', 'generation', 'execution_epoch',
                     'configuration_ref', 'source_configuration_ref'):
            if getattr(checked, name) != getattr(source, name):
                raise ValueError('source selection scope or version differs')
        if not source.not_before <= checked.effective_from < checked.effective_until <= source.expires_at:
            raise ValueError('event policy exceeds source selection validity')
