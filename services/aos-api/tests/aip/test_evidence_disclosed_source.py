"""Original request/actor/lease binding for internal source materialization."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked,
)
from aos_api.aip_production_contracts import (
    DisclosureLevel, DisclosureStatus, ResolveEvidenceDisclosureRequest,
)
from aos_api.tenant_scope import TenantScope
from aos_api.aip_production_contract_store import canonical_hash


@pytest.fixture
def setup_reader(monkeypatch):
    scope = TenantScope('org-org', 'dev-project')
    payload = {'summary': '真实正文结构的合成样本' * 100, 'marking': ['public']}
    payload_hash = canonical_hash(payload)
    body = ResolveEvidenceDisclosureRequest.model_validate({
        'evidenceRef': {'resourceType': 'Evidence', 'resourceId': 'ev-test',
                        'revision': 1, 'contentHash': payload_hash},
        'purpose': 'source', 'requestedLevel': 'l3', 'taskId': 'task-original',
    })
    decision = SimpleNamespace(
        created_by='actor', status=DisclosureStatus.ALLOWED,
        requested_level=DisclosureLevel.L3, granted_level=DisclosureLevel.L3,
        purpose='source', evidence_ref=body.evidence_ref,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        decision_hash='b' * 64,
    )
    state = SimpleNamespace(receipt=True, hash=payload_hash, reads=0, checks=0,
                            deny_on=0, expire_on=0)

    class Connection:
        def execute(self, sql, params):
            assert params[:2] == scope.key
            if 'aip_production_contract_receipt' in sql:
                assert params[2] == 'actor'
                original_hash = canonical_hash(body.model_dump(mode='json', by_alias=True))
                return SimpleNamespace(fetchone=lambda: {'receipt_id': 'r'}
                    if state.receipt and params[3] == original_hash else None)
            assert 'FROM aip_evidence' in sql
            state.reads += 1
            return SimpleNamespace(fetchone=lambda: {'content_hash': state.hash, 'payload': payload})

    store = AipProductionContractStore()
    monkeypatch.setattr(store, 'get_evidence_disclosure', lambda *a, **k: decision)

    def current(*args, **kwargs):
        assert kwargs['markings'] == ['public', 'secret']
        state.checks += 1
        if state.expire_on == state.checks:
            decision.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        return SimpleNamespace(
            status=DisclosureStatus.BLOCKED if state.deny_on == state.checks else DisclosureStatus.ALLOWED,
            granted_level=DisclosureLevel.L3,
        )

    monkeypatch.setattr(store, '_evaluate_disclosure', current)
    def read(**overrides):
        options = dict(conn=Connection(), scope=scope, actor='actor', decision_id='decision',
                       body=body, markings=['public', 'secret'])
        options.update(overrides)
        return store.read_disclosed_evidence_source(**options)
    return read, decision, state, body, payload


def test_source_is_complete_and_bound_to_existing_lease(setup_reader):
    read, decision, state, body, payload = setup_reader
    result = read()
    assert result['payload'] == payload
    assert len(result['payload']['summary']) > 200
    assert result['expiresAt'] == decision.expires_at.isoformat()
    assert result['evidenceRef'] == body.evidence_ref.model_dump(mode='json', by_alias=True)
    assert state.checks == 2


def test_source_denies_body_drift_even_when_registered_hash_still_matches(setup_reader):
    read, _, state, body, payload = setup_reader
    assert state.hash == body.evidence_ref.content_hash
    payload['summary'] = 'changed body with unchanged registered hash'
    with pytest.raises(ProductionContractDependencyBlocked, match='EVIDENCE_SOURCE_DISCLOSURE_DENIED'):
        read()


@pytest.mark.parametrize('failure', ['actor', 'task', 'receipt', 'expired', 'level', 'status',
                                     'hash', 'initial_policy', 'final_policy', 'final_expiry'])
def test_source_denies_invalid_or_changed_authority(setup_reader, failure):
    read, decision, state, body, _ = setup_reader
    options = {}
    if failure == 'actor': options['actor'] = 'other'
    elif failure == 'task': options['body'] = body.model_copy(update={'task_id': 'other'})
    elif failure == 'receipt': state.receipt = False
    elif failure == 'expired': decision.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif failure == 'level': decision.granted_level = DisclosureLevel.L2
    elif failure == 'status': decision.status = DisclosureStatus.BLOCKED
    elif failure == 'hash': state.hash = 'c' * 64
    elif failure == 'initial_policy': state.deny_on = 1
    elif failure == 'final_policy': state.deny_on = 2
    elif failure == 'final_expiry': state.expire_on = 2
    with pytest.raises(ProductionContractDependencyBlocked, match='EVIDENCE_SOURCE_DISCLOSURE_DENIED'):
        read(**options)
