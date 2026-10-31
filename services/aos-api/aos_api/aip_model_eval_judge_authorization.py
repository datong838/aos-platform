"""Inputs for a pending Judge-call application, never an execution token."""
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.asset_registry.contracts import BundleArtifact


class ModelJudgeRuleSourceRef(AipContractModel):
    publisher: str = Field(strict=True, pattern=r'^[a-z0-9]+(?:[.-][a-z0-9]+)*$', max_length=120)
    bundle_id: str = Field(strict=True, pattern=r'^[a-z0-9]+(?:[.-][a-z0-9]+)*$', max_length=120)
    version: str = Field(strict=True, min_length=1, max_length=200)
    content_hash: str = Field(strict=True, pattern=r'^sha256:[0-9a-f]{64}$')
    rule_artifact: BundleArtifact
    template_artifact: BundleArtifact
    implementation_artifact: BundleArtifact

    @model_validator(mode='after')
    def _distinct_artifacts(self):
        from aos_api.asset_registry.semver import parse_version
        parse_version(self.version)
        artifacts=(self.rule_artifact,self.template_artifact,self.implementation_artifact)
        if len({a.relative_path for a in artifacts})!=3 or any(a.size<=0 or a.size>1048576 for a in artifacts):
            raise ValueError('three distinct bounded original artifacts required')
        return self


class ModelJudgeRuleDefinition(AipContractModel):
    schema_version: Literal['aos.model-judge-rule/v1']
    judge_id: str = Field(strict=True,min_length=1,max_length=200)
    revision: int = Field(strict=True,ge=1)
    model_ref: VersionedAssetRef
    template_version: str = Field(strict=True,min_length=1,max_length=200)
    implementation_version: str = Field(strict=True,min_length=1,max_length=200)
    template_digest: str = Field(strict=True,pattern=r'^sha256:[0-9a-f]{64}$')
    implementation_digest: str = Field(strict=True,pattern=r'^sha256:[0-9a-f]{64}$')
    input_protocol: Literal['aos.model-eval-judge-input/v1']
    output_protocol: Literal['aos.model-judge-verdict/v1']

    @field_validator('model_ref',mode='before')
    @classmethod
    def _native_model_revision(cls,value):
        raw=value.model_dump() if isinstance(value,VersionedAssetRef) else value
        if not isinstance(raw,dict) or type(raw.get('revision')) is not int:
            raise ValueError('native original Model revision required')
        return value

    @model_validator(mode='after')
    def _rule_shape(self):
        from aos_api.asset_registry.semver import parse_version
        parse_version(self.template_version);parse_version(self.implementation_version)
        if self.model_ref.asset_type!='RegisteredModelRevision' or self.judge_id.strip()!=self.judge_id:
            raise ValueError('exact RegisteredModel Judge rule required')
        return self


class ModelJudgeCallRequestInput(AipContractModel):
    target_request_id: str = Field(strict=True, min_length=1, max_length=200)
    target_request_hash: str = Field(strict=True, pattern=r'^[0-9a-f]{64}$')
    target_approval_event_id: str = Field(strict=True, min_length=1, max_length=200)
    judge_request_id: str = Field(strict=True, min_length=1, max_length=200)
    judge_request_hash: str = Field(strict=True, pattern=r'^[0-9a-f]{64}$')
    judge_approval_event_id: str = Field(strict=True, min_length=1, max_length=200)
    upper_bound_minor: int = Field(strict=True, gt=0, le=100_000_000)
    expires_at: datetime

    @field_validator('target_request_id', 'judge_request_id',
                     'target_approval_event_id', 'judge_approval_event_id')
    @classmethod
    def _exact_identifier(cls, value: str) -> str:
        if value.strip() != value:
            raise ValueError('exact original identifier required')
        return value

    @model_validator(mode='after')
    def _distinct_sources(self):
        if self.target_request_id == self.judge_request_id or self.expires_at.utcoffset() is None:
            raise ValueError('distinct original requests and aware expiry required')
        return self


class ModelJudgeCallRuleRequestInput(ModelJudgeCallRequestInput):
    """Mandatory original signed rule source; v1 requests cannot be upgraded."""
    schema_version: Literal['aos.model-judge-call-input/v2'] = 'aos.model-judge-call-input/v2'
    rule_source: ModelJudgeRuleSourceRef
