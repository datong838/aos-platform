"""Disposable PG and TLS/JWT proof; no formal identity or live activation claim."""
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime, timedelta
import uuid

import pytest

from aos_api.aip_action_store import canonical_hash, proposal_request_hash
from aos_api.aip_network_policy_action_producer import NetworkActivationProposalRequest
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_proposal_reconcile import (
    ProposalInquiryBlocked, inquire_network_proposal,
)
from aos_api.auth import Principal
from aos_api.db import connect, connect_read_only
from aos_api.tenant_scope import TenantScope
from tests.aip.test_network_approval_precheck_expiry_pg import _approved
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_consumer_application import client
from tests.aip.test_network_consumer_signed_https_pg import https_signer


URL = '/v1/aip/runtime-guard-policies/networks/activation-proposals'


def saved_request(expiring=None):
    proposal, _, _, expiry = _approved(expiring)
    with isolated_owner() as conn:
        row = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s '
                           'AND proposal_id=%s', (*SCOPE.key, proposal)).fetchone()
    body = NetworkActivationProposalRequest(candidate=NetworkPolicyRevisionCreate.model_validate(
        row['payload']['candidate']), expiresAt=row['expires_at'])
    principal = Principal(row['created_by'], *SCOPE.key, ['owner'], token_kind='oidc')
    return row, body, principal, expiry


def inquire(row, body, principal, **kwargs):
    return inquire_network_proposal(principal, body, expected_version=0,
                                    idempotency_key=row['idempotency_key'], **kwargs)


def counts():
    with isolated_owner() as conn:
        return tuple(conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n']
                     for table in ('aip_action_proposal', 'aip_action_draft',
                                   'aip_action_approval_event', 'aip_network_policy_head',
                                   'aip_network_policy_revision', 'aip_network_policy_receipt'))


def test_exact_original_request_observed_in_readonly_transaction_without_writes():
    row, body, principal, _ = saved_request()
    before = counts()
    @contextmanager
    def checked(scope):
        with connect_read_only(scope) as conn:
            assert conn.read_only is True
            assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
            assert conn.execute('SHOW transaction_isolation').fetchone()['transaction_isolation'] == 'repeatable read'
            yield conn
    for _ in range(2):
        assert inquire(row, body, principal, connect_factory=checked) == {
            'status': 'observed', 'proposalId': row['proposal_id']}
    assert counts() == before


@pytest.mark.parametrize('drift', ['candidate', 'expiry', 'version'])
def test_same_key_different_original_input_is_conflict_without_id(drift):
    row, body, principal, _ = saved_request()
    if drift == 'candidate':
        body = body.model_copy(update={'candidate': body.candidate.model_copy(update={'owner': 'different'})})
    if drift == 'expiry':
        body = body.model_copy(update={'expires_at': body.expires_at+timedelta(seconds=1)})
    result = inquire_network_proposal(principal, body, expected_version=1 if drift == 'version' else 0,
                                     idempotency_key=row['idempotency_key'])
    assert result == {'status': 'conflict'}


@pytest.mark.parametrize('missing', ['key', 'actor', 'tenant'])
def test_unseen_or_inaccessible_record_is_unresolved_not_permission_to_resend(missing):
    row, body, principal, _ = saved_request()
    if missing == 'key':
        row['idempotency_key'] = 'unseen-'+uuid.uuid4().hex
    if missing == 'actor':
        principal = Principal('other-maker', *SCOPE.key, ['owner'], token_kind='oidc')
    if missing == 'tenant':
        principal = Principal(principal.subject, 'dev-org', SCOPE.project_id, ['owner'], token_kind='oidc')
    before = counts()
    assert inquire(row, body, principal) == {'status': 'unresolved'}
    assert counts() == before


def test_expired_proposal_and_revoked_membership_do_not_erase_historical_observation():
    row, body, principal, expiry = saved_request('proposal')
    with isolated_owner() as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, principal.subject))
        remaining = max(0, (expiry-datetime.now(UTC)).total_seconds())
        conn.execute('SELECT pg_sleep(%s)', (remaining+.05,))
    assert datetime.now(UTC) > body.expires_at
    before = counts()
    assert inquire(row, body, principal) == {'status': 'observed', 'proposalId': row['proposal_id']}
    assert counts() == before


def test_uncommitted_creation_stays_unresolved_then_observed_after_original_commit():
    from aos_api.aip_network_policy_action_producer import propose_network_activation
    row, original, principal, _ = saved_request()
    key = 'pending-'+uuid.uuid4().hex
    body = original.model_copy(update={'candidate': original.candidate.model_copy(
        update={'policy_id': 'pending-policy-'+uuid.uuid4().hex})})
    with connect(SCOPE) as conn:
        created = propose_network_activation(principal, body.candidate, expected_version=0,
            idempotency_key=key, expires_at=body.expires_at,
            connect_factory=lambda scope: nullcontext(conn))
        assert inquire_network_proposal(principal, body, expected_version=0,
                                        idempotency_key=key) == {'status': 'unresolved'}
    before = counts()
    assert inquire_network_proposal(principal, body, expected_version=0, idempotency_key=key) == {
        'status': 'observed', 'proposalId': created.proposal.id}
    assert counts() == before


@pytest.mark.parametrize('factory', [connect, lambda scope: connect_read_only(TenantScope('dev-org', scope.project_id))])
def test_writeable_or_wrong_scope_connection_denied(factory):
    row, body, principal, _ = saved_request()
    with pytest.raises(ProposalInquiryBlocked, match='READ_IDENTITY_REQUIRED'):
        inquire(row, body, principal, connect_factory=factory)


def test_dev_identity_rejected_before_database():
    from tests.aip.test_aip_network_policy_action_producer import _candidate
    principal = Principal('user:dev', *SCOPE.key, ['admin'], token_kind='dev')
    body = NetworkActivationProposalRequest(candidate=_candidate(), expiresAt=datetime.now(UTC))
    with pytest.raises(ProposalInquiryBlocked, match='OIDC_POLICY_MAKER_REQUIRED'):
        inquire_network_proposal(principal, body, expected_version=0, idempotency_key='key',
            connect_factory=lambda scope: pytest.fail('must not open database'))


def test_extracted_request_hash_preserves_original_formula():
    from aos_api.aip_action_models import CreateActionProposalRequest
    body = CreateActionProposalRequest(actionTypeId='ordinary-action', purpose='original hash')
    policy = {'floor': 'R2', 'makerChecker': True}
    assert proposal_request_hash(body, 'a'*64, 'R2', policy) == canonical_hash({
        'request': body.model_dump(mode='json', by_alias=True),
        'actionTypeRevisionHash': 'a'*64, 'classifiedRiskLevel': 'R2', 'policy': policy})


def test_real_signed_http_created_proposal_can_be_found_without_reposting(client, https_signer):
    row, original, principal, _ = saved_request()
    sign, fetched = https_signer
    headers = {'Authorization': 'Bearer '+sign(principal.subject), 'X-Org-Id': SCOPE.org_id,
               'X-Project-Id': SCOPE.project_id, 'If-Match': '0', 'Idempotency-Key': uuid.uuid4().hex}
    body = original.model_copy(update={'candidate': original.candidate.model_copy(
        update={'policy_id': 'inquiry-http-'+uuid.uuid4().hex})}).model_dump(mode='json', by_alias=True)
    created = client.post(URL, headers=headers, json=body)
    assert created.status_code == 201, created.text
    proposal_id = created.json()['proposal']['id']
    before = counts()
    for _ in range(2):
        result = client.post(URL+'/inquiry', headers=headers, json=body)
        assert result.status_code == 200, result.text
        assert result.json() == {'status': 'observed', 'proposalId': proposal_id}
    changed = {**body, 'expiresAt': (original.expires_at+timedelta(seconds=1)).isoformat()}
    assert client.post(URL+'/inquiry', headers=headers, json=changed).status_code == 409
    assert client.post(URL+'/inquiry', headers={**headers, 'Idempotency-Key': 'absent'}, json=body).status_code == 202
    assert client.post(URL+'/inquiry', headers=headers, json={**body, 'orgId': 'other'}).status_code == 400
    assert counts() == before
    assert fetched


def test_database_failure_is_503_not_unresolved(client, https_signer, monkeypatch):
    from aos_api import aip_network_proposal_reconcile as module
    row, body, principal, _ = saved_request()
    sign, _ = https_signer
    def unavailable(scope):
        raise RuntimeError('private connection detail must not leak')
    monkeypatch.setattr(module, 'db_connect_read_only', unavailable)
    response = client.post(URL+'/inquiry', headers={
        'Authorization': 'Bearer '+sign(principal.subject), 'If-Match': '0',
        'X-Org-Id': SCOPE.org_id, 'X-Project-Id': SCOPE.project_id,
        'Idempotency-Key': row['idempotency_key']}, json=body.model_dump(mode='json', by_alias=True))
    assert response.status_code == 503
    assert response.json()['code'] == 'NETWORK_PROPOSAL_INQUIRY_UNAVAILABLE'
    assert 'private connection detail' not in response.text
