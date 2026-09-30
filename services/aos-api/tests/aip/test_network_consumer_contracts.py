"""No-effect transport contract; not OIDC or business authorization proof."""
import pytest
from pydantic import ValidationError
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry


def raw(**changes):
    return {'schemaVersion': 1, 'bearerToken': 'header.payload.signature',
            'orgId': 'org-org', 'projectId': 'dev-project', 'proposalId': 'proposal-1',
            'proposalHash': 'a'*64, 'approvalEventId': 'approval-1',
            'targetContentHash': 'b'*64, 'bindingHash': 'c'*64, **changes}


def test_command_exact_inquiry_and_secret_redaction():
    command = NetworkConsumerCommand.model_validate(raw())
    inquiry = command.inquiry()
    assert type(inquiry) is NetworkConsumerInquiry and inquiry.matches(command)
    assert command.idempotency_key == 'proposal-1'
    assert inquiry.request_hash == command.request_hash
    assert 'header.payload.signature' not in repr(command)
    assert 'header.payload.signature' not in command.model_dump_json()
    refreshed = NetworkConsumerCommand.model_validate(raw(bearerToken='new.payload.signature'))
    assert inquiry.matches(refreshed)
    assert command.request_hash == refreshed.request_hash


@pytest.mark.parametrize('changes', [
    {'actorId': 'forged'}, {'roles': ['owner']}, {'idempotencyKey': 'retry'}, {'candidate': {}},
    {'dsn': 'untrusted'}, {'bearerToken': 'dev'}, {'schemaVersion': True},
    {'orgId': ' org-org'}, {'proposalId': 'proposal 1'}, {'approvalEventId': ''},
    {'proposalHash': 'short'}, {'bindingHash': 'Z'*64}, {'targetContentHash': 'a'*63},
])
def test_untrusted_or_coerced_shape_rejected(changes):
    with pytest.raises(ValidationError):
        NetworkConsumerCommand.model_validate(raw(**changes))


@pytest.mark.parametrize('field,value', [
    ('orgId','other'), ('projectId','other'), ('proposalId','other'), ('approvalEventId','other'),
    ('proposalHash','d'*64), ('targetContentHash','d'*64), ('bindingHash','d'*64),
])
def test_every_exact_reference_is_bound(field, value):
    command = NetworkConsumerCommand.model_validate(raw())
    changed = NetworkConsumerCommand.model_validate(raw(**{field: value}))
    assert command.request_hash != changed.request_hash
    assert not command.inquiry().matches(changed)
