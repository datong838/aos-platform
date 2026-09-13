"""Derived exact SkillBinding set; it carries no independent execution authority."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictInt, model_validator
from aos_api.aip_agent_registry_contracts import SkillBinding
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_scope import TenantScope


class AnalysisSkillBindingSet(AipContractModel):
    schema_version: Literal['aos.ecommerce.analysis-skill-binding-set/v1'] = 'aos.ecommerce.analysis-skill-binding-set/v1'
    tenant: TenantContext
    installation_id: UUID
    generation: UUID
    execution_epoch: StrictInt = Field(gt=0)
    responsibility_plan_ref: ExactRevisionRef
    bindings: tuple[SkillBinding, ...] = Field(min_length=1, max_length=128)
    content_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @model_validator(mode='after')
    def exact_set(self):
        if canonical_sha256(self.model_dump(mode='json', by_alias=True, exclude={'content_hash'})) != self.content_hash:
            raise ValueError('skill binding set hash differs')
        if self.responsibility_plan_ref.resource_type != 'ResponsibilityPlanRevision':
            raise ValueError('exact responsibility plan required')
        ids = [item.binding_id for item in self.bindings]
        skills = [item.skill.asset_id for item in self.bindings]
        if ids != sorted(set(ids)) or len(skills) != len(set(skills)):
            raise ValueError('binding set must be unique and canonically ordered')
        if any(item.tenant != self.tenant or item.skill.asset_type != 'SkillTemplate' for item in self.bindings):
            raise ValueError('binding tenant or skill type differs')
        return self

    @property
    def exact_ref(self):
        digest = self.content_hash.removeprefix('sha256:')
        return ExactRevisionRef(resourceType='SkillBindingSetRevision',
            resourceId='analysis-skill-set-' + digest, revision=1, contentHash=digest)

    def validate_current(self, *, scope, installation_id, generation, execution_epoch,
                         responsibility_ref, bindings, now):
        current = type(self).model_validate(self.model_dump(mode='json', by_alias=True))
        if (type(scope) is not TenantScope or type(installation_id) is not UUID
                or type(generation) is not UUID or type(execution_epoch) is not int
                or (current.tenant.org_id, current.tenant.project_id) != scope.key
                or (current.installation_id, current.generation, current.execution_epoch)
                    != (installation_id, generation, execution_epoch)
                or current.responsibility_plan_ref != responsibility_ref):
            raise ValueError('current skill set installation or responsibility differs')
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError('aware current time required')
        if not isinstance(bindings, (list, tuple)) or any(type(item) is not SkillBinding for item in bindings):
            raise ValueError('current authoritative bindings required')
        observed = tuple(SkillBinding.model_validate(item.model_dump(mode='json', by_alias=True))
                         for item in sorted(bindings, key=lambda value: value.binding_id))
        if observed != current.bindings:
            raise ValueError('current skill binding set differs')
        for item in observed:
            if (item.status != 'active' or item.readiness.value != 'available' or item.readiness_reasons
                    or not item.dependency_snapshot_hash or item.last_evaluated_at is None
                    or item.last_evaluated_at.tzinfo is None or item.last_evaluated_at > now
                    or item.readiness_expires_at is None or item.readiness_expires_at.tzinfo is None
                    or item.readiness_expires_at <= now):
                raise ValueError('current skill binding readiness is unavailable or expired')
        return current.exact_ref
