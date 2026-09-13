"""Reject attempts to smuggle identity, execution or stale/ambiguous targets."""
import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from aos_api.extension_runtime.configuration_stage_contracts import ConfigurationStageRequest


def request():
    return dict(schemaVersion='aos.runtime-configuration-stage/v1', action='stage-configuration',
                target=dict(installationId='97aeb2e7-59ba-40f6-89a3-fb0293bc0497',
                            installationEtag=5, generation='3a445eee-aa28-4459-9e5a-f12a806a94b1',
                            bindingRevision=4),
                roleRefs=[dict(authority='aip.responsibility_plan_revision', id='roles',
                               revision=1, hash='sha256:'+'a'*64)],
                policyRef=dict(authority='aip.runtime_policy_revision', id='policy',
                               revision=1, hash='sha256:'+'b'*64))


def parse(value):
    return ConfigurationStageRequest.model_validate_json(json.dumps(value))


def test_exact_request_roundtrips_without_identity_or_execution_fields():
    value = parse(request())
    assert parse(value.model_dump(mode='json')) == value
    assert value.previousRef is None


@pytest.mark.parametrize('field', ('subject', 'orgId', 'projectId', 'deadline', 'requestId',
                                  'dataRefs', 'budgetRef', 'permissions', 'state', 'payload'))
def test_client_cannot_supply_server_identity_or_derived_authority(field):
    value = request()
    value[field] = 'untrusted'
    with pytest.raises(ValidationError): parse(value)


@pytest.mark.parametrize('field', ('installationEtag', 'bindingRevision'))
@pytest.mark.parametrize('version', (True, 0, -1, '5', 2**63))
def test_target_versions_reject_coercion_and_overflow(field, version):
    value = request()
    value['target'][field] = version
    with pytest.raises(ValidationError): parse(value)


@pytest.mark.parametrize('field', ('installationId', 'generation'))
def test_noncanonical_target_is_not_silently_normalized(field):
    value = request()
    value['target'][field] = value['target'][field].upper()
    with pytest.raises(ValidationError): parse(value)


@pytest.mark.parametrize('case', ('empty', 'duplicate', 'other_revision', 'too_many',
                                  'role_authority', 'policy_authority', 'enable'))
def test_ambiguous_sources_and_action_expansion_are_rejected(case):
    value = request()
    role = value['roleRefs'][0]
    if case == 'empty': value['roleRefs'] = []
    elif case == 'duplicate': value['roleRefs'].append(deepcopy(role))
    elif case == 'other_revision': value['roleRefs'].append(dict(role, revision=2))
    elif case == 'too_many': value['roleRefs'] = [dict(role, id=f'role-{i}') for i in range(65)]
    elif case == 'role_authority': role['authority'] = 'arbitrary.roles'
    elif case == 'policy_authority': value['policyRef']['authority'] = 'arbitrary.policy'
    elif case == 'enable': value['action'] = 'enable'
    with pytest.raises(ValidationError): parse(value)


def test_existing_model_instance_does_not_bypass_nested_target_validation():
    valid = parse(request())
    changed = valid.model_copy(update={'target': valid.target.model_copy(update={'bindingRevision': True})})
    with pytest.raises(ValidationError): ConfigurationStageRequest.model_validate(changed)
