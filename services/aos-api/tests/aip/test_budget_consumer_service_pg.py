"""Real isolated PG and signed HTTPS identity; no live activation or Provider."""
import pytest
from pydantic import SecretStr

from aos_api.aip_budget_consumer_service import (
    BudgetConsumerRequest, BudgetConsumerServiceBlocked, consume_budget_once, inquire_budget,
)
from aos_api.aip_budget_consumer_connection import connect_budget_consumer, BudgetConsumerBlocked
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer
from tests.aip.test_budget_consumer_connection_pg import configured
from tests.aip.test_budget_cost_consumer_pg import approved, counts
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


@pytest.fixture
def case(configured, issuer_factory, https_signer, tmp_path):
    maker, checker, p, saved, decision = approved(issuer_factory, https_signer)
    request = BudgetConsumerRequest(schemaVersion=1, orgId=SCOPE.org_id, projectId=SCOPE.project_id,
        proposalId=saved['proposalId'], proposalHash=saved['proposalHash'], decisionId=decision['decisionId'],
        bearerToken=https_signer[0](maker.subject))
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    return maker, checker, p, saved, decision, request, attempts


def test_consume_once_and_revoked_history_remains_readable(case, configured, issuer_factory, https_signer):
    maker, _, p, saved, _, request, attempts = case
    assert inquire_budget(request, configured) == {'status': 'unresolved'}
    result = consume_budget_once(request, configured, attempts)
    assert result['status'] == 'observed' and result['activationEligible'] is False
    assert counts(p) == dict(active=1, receipts=1)
    marker = next(attempts.iterdir()).read_text()
    assert request.bearer_token.get_secret_value() not in marker
    assert consume_budget_once(request, configured, attempts) == result
    BudgetCostIssuer(issuer_factory).execute(command(https_signer[0], maker, saved,
        operation='revoke', decision=None, reason='withdraw after consume'))
    assert inquire_budget(request, configured) == result
    assert counts(p) == dict(active=1, receipts=1)


@pytest.mark.parametrize('drift', ['checker', 'hash', 'tenant', 'expired', 'signature', 'membership'])
def test_identity_and_exact_reference_fail_before_attempt(drift, case, configured, https_signer):
    maker, checker, p, _, _, request, attempts = case
    if drift == 'checker':
        request = request.model_copy(update={'bearer_token': SecretStr(https_signer[0](checker.subject))})
    elif drift == 'hash':
        request = request.model_copy(update={'proposal_hash': '0'*64})
    elif drift == 'tenant':
        request = request.model_copy(update={'org_id': 'dev-org'})
    elif drift in ('expired', 'signature'):
        token = https_signer[0](maker.subject, changes={'exp': 1} if drift == 'expired' else {}, wrong_key=drift == 'signature')
        request = request.model_copy(update={'bearer_token': SecretStr(token)})
    else:
        with isolated_owner() as conn:
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s', (*SCOPE.key, maker.subject))
            conn.commit()
    with pytest.raises((BudgetConsumerServiceBlocked, BudgetConsumerBlocked)):
        consume_budget_once(request, configured, attempts)
    assert not list(attempts.iterdir()) and counts(p) == dict(active=0, receipts=0)


def test_commit_response_loss_only_reconciles(case, configured, monkeypatch):
    from contextlib import contextmanager
    import aos_api.aip_budget_consumer_service as service
    _, _, p, _, _, request, attempts = case
    original = service.connect_budget_consumer
    writes = []
    @contextmanager
    def lose_response(config, scope, *, read_only=False):
        with original(config, scope, read_only=read_only) as conn:
            yield conn
        if not read_only:
            writes.append(True)
            raise ConnectionError('injected after real commit')
    monkeypatch.setattr(service, 'connect_budget_consumer', lose_response)
    result = service.consume_budget_once(request, configured, attempts)
    assert result['status'] == 'observed'
    assert service.consume_budget_once(request, configured, attempts) == result
    assert writes == [True] and counts(p) == dict(active=1, receipts=1)


@pytest.mark.parametrize('corrupt', [False, True])
def test_attempted_or_unknown_without_receipt_never_reexecutes(corrupt, case, configured):
    from aos_api.aip_network_issuer_attempt import _reserve_attempt_receipt, AttemptReceipt
    maker, _, p, _, _, request, attempts = case
    _reserve_attempt_receipt(attempts, AttemptReceipt(request.org_id, request.project_id,
        request.proposal_id, request.proposal_id, request.request_hash, maker.subject),
        namespace='budget-cost-consumer/v1')
    if corrupt:
        next(attempts.iterdir()).write_text('{')
    assert consume_budget_once(request, configured, attempts) == {'status': 'unresolved'}
    assert counts(p) == dict(active=0, receipts=0)


def test_raw_consumer_permission_removed_and_inquiry_requires_read_only(case, configured):
    _, _, p, saved, decision, request, _ = case
    for read_only, query, values in [
        (False, 'SELECT public.aip_consume_budget_cost_a0v_126(%s,%s,%s,%s)', (*SCOPE.key, saved['proposalId'], decision['decisionId'])),
        (False, 'SELECT public.aip_reconcile_budget_as_actor_a0v_127(%s,%s,%s,%s,%s,%s)',
         (*SCOPE.key, saved['proposalId'], decision['decisionId'], saved['proposal']['makerSubject'], saved['proposalHash'])),
    ]:
        with pytest.raises(BudgetConsumerBlocked):
            with connect_budget_consumer(configured, SCOPE, read_only=read_only) as conn:
                conn.execute(query, values)
    assert counts(p) == dict(active=0, receipts=0)


def test_historical_receipt_does_not_require_current_provider_or_head_but_requires_member(case, configured):
    maker, _, p, _, _, request, attempts = case
    result = consume_budget_once(request, configured, attempts)
    with isolated_owner() as conn:
        conn.execute('UPDATE aip_budget_head SET version=version+1 WHERE org_id=%s AND project_id=%s AND budget_id=%s',
                     (*SCOPE.key, p.target.budget_id))
        conn.execute('UPDATE aip_provider_instance_head SET current_revision=999 WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s',
                     (*SCOPE.key, p.basis.provider.asset_id))
        conn.commit()
    assert inquire_budget(request, configured) == result
    with isolated_owner() as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s', (*SCOPE.key, maker.subject))
        conn.commit()
    with pytest.raises(BudgetConsumerBlocked):
        inquire_budget(request, configured)
    assert counts(p) == dict(active=1, receipts=1)


def test_receipt_corruption_is_conflict_not_new_activation(case, configured):
    _, _, p, saved, _, request, attempts = case
    assert consume_budget_once(request, configured, attempts)['status'] == 'observed'
    with isolated_owner() as conn:
        # Deliberate corruption in the disposable fixture, re-enable schema gates
        # before readback; proves row evidence is checked as well as catalog shape.
        conn.execute('ALTER TABLE aip_budget_receipt DISABLE TRIGGER USER')
        conn.execute("UPDATE aip_budget_receipt SET result_ref=result_ref || '{\"extra\":true}'::jsonb "
                     "WHERE org_id=%s AND project_id=%s AND operation='budget_revision.activate_cost' AND idempotency_key=%s",
                     (*SCOPE.key, saved['proposalId']))
        conn.execute('ALTER TABLE aip_budget_receipt ENABLE TRIGGER USER')
        conn.commit()
    assert inquire_budget(request, configured) == {'status': 'conflict'}
    assert consume_budget_once(request, configured, attempts) == {'status': 'conflict'}
    assert counts(p) == dict(active=1, receipts=1)


def test_request_cannot_supply_actor_or_dev_identity(case):
    from pydantic import ValidationError
    request = case[-2]
    for changes in ({'actor': 'other'}, {'org_id': 'dev-org'}, {'schema_version': True},
                    {'bearer_token': SecretStr('dev-token')}, {'decision_id': ' leading'}):
        with pytest.raises(ValidationError):
            BudgetConsumerRequest.model_validate({**request.model_dump(), **changes})


def test_concurrent_same_request_has_one_write_attempt(case, configured, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import aos_api.aip_budget_consumer_service as service
    _, _, p, _, _, request, attempts = case
    start = Barrier(2)
    original = service._call
    writes = []
    def counted(conn, request, subject, *, read_only):
        if not read_only:
            writes.append(True)
        return original(conn, request, subject, read_only=read_only)
    monkeypatch.setattr(service, '_call', counted)
    def run():
        start.wait(timeout=5)
        return consume_budget_once(request, configured, attempts)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(run), pool.submit(run)
        assert all(r['status'] in {'observed', 'unresolved'} for r in (a.result(timeout=15), b.result(timeout=15)))
    assert writes == [True] and counts(p) == dict(active=1, receipts=1)
    assert inquire_budget(request, configured)['status'] == 'observed'
