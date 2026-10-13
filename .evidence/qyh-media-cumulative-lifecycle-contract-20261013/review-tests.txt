"""A populated original lifecycle must remain representable by cumulative v6."""
import pytest
from pydantic import ValidationError
from aos_api.ecommerce_workshop_media_studio import EcommerceWorkshopMediaStudio
from aos_api.ecommerce_workshop_media_cumulative import EcommerceWorkshopMediaCumulative
from aos_api.ecommerce_workshop_media_studio_contracts import (
    WorkshopMediaStudioViewEnvelope, MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION,
    MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION, MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION,
    MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION, MEDIA_STUDIO_SCHEMA_VERSION,
)
from test_ecommerce_workshop_media_studio_lifecycle import composer, CUTOFF


def populated(*, cumulative=True):
    lifecycle, _ = composer()
    return EcommerceWorkshopMediaStudio(
        lifecycle=lifecycle,
        cumulative=EcommerceWorkshopMediaCumulative() if cumulative else None,
        clock=lambda: CUTOFF,
    ).read(org_id='org-org', project_id='dev-project')


def test_v6_keeps_existing_lifecycle_and_external_gates():
    view = populated()
    assert view.schema_version == MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION
    assert view.lifecycle.context_id == 'context-1'
    assert view.lifecycle_status == 'ready'
    assert view.lifecycle.external_effects_allowed is False
    assert all(c.allowed is False for c in view.lifecycle.command_capabilities)
    assert view.cumulative_gate_set.external_effects_allowed is False
    assert view.cumulative_gate_set.release_allowed is False
    assert view.cumulative_gate_set.overall_status == 'blocked'


@pytest.mark.parametrize('schema', [MEDIA_STUDIO_PROVIDER_SCHEMA_VERSION, MEDIA_STUDIO_SCHEMA_VERSION])
def test_legacy_v2_v3_still_reject_lifecycle(schema):
    raw = populated(cumulative=False).model_dump(mode='json', by_alias=True)
    raw['schemaVersion'] = schema
    with pytest.raises(ValidationError, match='legacy media view cannot carry v4 lifecycle'):
        WorkshopMediaStudioViewEnvelope.model_validate(raw)


@pytest.mark.parametrize('schema', [MEDIA_STUDIO_LIFECYCLE_SCHEMA_VERSION, MEDIA_STUDIO_PUBLISH_SCHEMA_VERSION])
def test_original_v4_v5_lifecycle_remains_valid(schema):
    raw = populated(cumulative=False).model_dump(mode='json', by_alias=True)
    raw['schemaVersion'] = schema
    assert WorkshopMediaStudioViewEnvelope.model_validate(raw).lifecycle.context_id == 'context-1'


def test_v6_blocked_lifecycle_cannot_carry_contribution():
    raw = populated(cumulative=False).model_dump(mode='json', by_alias=True)
    raw['schemaVersion'] = MEDIA_STUDIO_CUMULATIVE_SCHEMA_VERSION
    raw['cumulativeGateSet'] = EcommerceWorkshopMediaCumulative().read(cutoff=CUTOFF).model_dump(mode='json', by_alias=True)
    raw['lifecycleStatus'] = 'blocked'
    raw['lifecycleBlockers'] = [{'code':'UNAVAILABLE','dependency':'lifecycle','requiredAction':'reconcile'}]
    with pytest.raises(ValidationError, match='blocked media lifecycle requires blockers and no contribution'):
        WorkshopMediaStudioViewEnvelope.model_validate(raw)
