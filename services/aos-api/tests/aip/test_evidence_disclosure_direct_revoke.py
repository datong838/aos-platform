"""Direct revocation must deny every disclosure layer before source consumption."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import ResolveEvidenceDisclosureRequest
from aos_api.tenant_scope import TenantScope


class Connection:
    def __init__(self, revoked=False, unavailable=False):
        self.revoked = revoked
        self.unavailable = unavailable
        self.checked = False

    def execute(self, sql, params):
        if 'FROM aip_evidence_revoke_event' in sql:
            assert params == ('org-org', 'dev-project', 'evidence-test', 1, 'a' * 64)
            assert all(part in sql for part in ('org_id=%s', 'project_id=%s', 'evidence_id=%s', 'revision=%s', 'content_hash=%s'))
            self.checked = True
            if self.unavailable:
                raise RuntimeError('revocation owner unavailable')
            return SimpleNamespace(fetchone=lambda: {'event_id': 'revoked'} if self.revoked else None)
        if 'FROM aip_evidence_bundle_revision' in sql:
            return SimpleNamespace(fetchall=lambda: [])
        assert 'FROM aip_evidence' in sql
        assert params == ('org-org', 'dev-project', 'evidence-test')
        now = datetime.now(timezone.utc)
        return SimpleNamespace(fetchone=lambda: dict(
            content_hash='a' * 64, payload={'summary': '合成来源'},
            source_type='database', source_ref='synthetic', evidence_type='query',
            observed_at=now, freshness_at=now,
        ))


def evaluate(conn, level):
    body = ResolveEvidenceDisclosureRequest.model_validate({
        'evidenceRef': {'resourceType': 'Evidence', 'resourceId': 'evidence-test',
                        'revision': 1, 'contentHash': 'a' * 64},
        'purpose': 'source', 'requestedLevel': level,
    })
    return AipProductionContractStore()._evaluate_disclosure(
        conn, TenantScope('org-org', 'dev-project'), 'test-actor', body,
        markings=['public', 'restricted', 'secret'],
    )


@pytest.mark.parametrize('level', ['l1', 'l2', 'l3'])
@pytest.mark.parametrize('revoked', [False, True])
def test_direct_revocation_controls_each_disclosure_layer(level, revoked):
    conn = Connection(revoked)
    decision = evaluate(conn, level)
    assert conn.checked
    if revoked:
        assert decision.status.value == 'blocked'
        assert 'EVIDENCE_REVOKED' in decision.reasons
        assert decision.granted_level is None
        assert decision.display_payload == {}
        assert decision.expires_at is None
        assert decision.redaction_receipt['bodyReturned'] is False
    else:
        assert decision.status.value == 'allowed'
        assert decision.granted_level.value == level
        assert decision.display_payload['layer'] == level


def test_revocation_lookup_failure_does_not_allow_disclosure():
    with pytest.raises(RuntimeError, match='revocation owner unavailable'):
        evaluate(Connection(unavailable=True), 'l3')
