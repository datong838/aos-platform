"""Isolated PG login + signed TLS JWT; no production authority or Provider call."""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql, IsolationLevel
from psycopg.rows import dict_row
import pytest

from aos_api.aip_budget_cost_issuer import BudgetCostIssuer, BudgetCostIssuerCommand, BudgetCostIssuerBlocked
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.tenant_scope import apply_transaction_scope
from aos_api.db import connect
from tests.aip.test_budget_cost_proposal_pg import case
from tests.aip.test_network_consumer_boundary_pg import isolated_owner,SCOPE
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer


@pytest.fixture
def issuer_factory(private_passfile):
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('budget-cost-issuer-tests'))")
        original=admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_budget_cost_issuer'").fetchone()
        assert original=={'rolcanlogin':False,'no_password':True}
        password=secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE aos_budget_cost_issuer LOGIN PASSWORD {}').format(sql.Literal(password)));admin.commit()
        host,port,database=admin.info.host,admin.info.port,admin.info.dbname
        private_passfile.write_text(f'{host}:{port}:{database}:aos_budget_cost_issuer:{password}\n')
        @contextmanager
        def factory(scope,read_only):
            with psycopg.connect(host=host,port=port,dbname=database,user='aos_budget_cost_issuer',
                passfile=str(private_passfile),row_factory=dict_row,
                options='-c statement_timeout=10000 -c lock_timeout=5000 -c idle_in_transaction_session_timeout=10000') as conn:
                conn.isolation_level=IsolationLevel.REPEATABLE_READ if read_only else IsolationLevel.SERIALIZABLE
                conn.read_only=read_only;apply_transaction_scope(conn,scope)
                yield conn
        try:yield factory
        finally:
            admin.execute('ALTER ROLE aos_budget_cost_issuer NOLOGIN PASSWORD NULL');admin.commit()
            private_passfile.write_text('# removed temporary issuer credential\n')
            assert admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password FROM pg_authid WHERE rolname='aos_budget_cost_issuer'").fetchone()==original
            admin.execute("SELECT pg_advisory_unlock(hashtext('budget-cost-issuer-tests'))")


def prepared(window=None):
    from tests.aip._runtime_guard_history_fixture import produce_formal_provider
    maker,checker,other,p,key=case();provider_id='issuer-provider-'+uuid4().hex
    provider=produce_formal_provider(SCOPE,maker.subject,provider_id)
    if window is not None:
        from aos_api.aip_budget_store import AipBudgetAuthorityStore
        from aos_api.aip_budget_contracts import BudgetLifecycle
        draft=p.target.model_copy(update={'lifecycle':BudgetLifecycle.DRAFT,
            'effective_until':datetime.now(UTC)+timedelta(seconds=window)})
        AipBudgetAuthorityStore().publish(SCOPE,maker.subject,'short-'+key,draft,expected_version=1)
        p.target=draft.model_copy(update={'lifecycle':BudgetLifecycle.ACTIVE,'revision':3})
        p.draft_revision=2;p.expected_head_version=2
    p.basis.provider=p.basis.provider.model_copy(update={'asset_id':provider_id,'content_hash':provider.content_hash})
    saved=BudgetCostProposalStore().create(maker,p,key)
    return maker,checker,other,p,saved


def command(sign,actor,saved,**changes):
    body=dict(operation='decide',orgId=SCOPE.org_id,projectId=SCOPE.project_id,bearerToken=sign(actor.subject),
        proposalId=saved['proposalId'],proposalHash=saved['proposalHash'],idempotencyKey='issuer-'+uuid4().hex,decision='approved')
    body.update(changes);return BudgetCostIssuerCommand.model_validate(body)


def test_signed_checker_decision_recovery_and_maker_revocation(issuer_factory,https_signer):
    sign,fetched=https_signer;maker,checker,_,p,saved=prepared();issuer=BudgetCostIssuer(issuer_factory)
    cmd=command(sign,checker,saved);approved=issuer.execute(cmd)
    assert approved['decision']=='approved' and approved['activationEligible'] is False
    assert issuer.execute(cmd)==approved
    assert issuer.inquire(cmd)==dict(status='observed',result=approved,activationEligible=False)
    revoked=command(sign,maker,saved,operation='revoke',decision=None,reason='withdraw risk')
    result=issuer.execute(revoked);assert result['decisionId']==approved['decisionId']
    assert issuer.execute(revoked)==result and issuer.inquire(revoked)['status']=='observed'
    assert issuer.inquire(cmd)['result']==approved
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_budget_revision WHERE budget_id=%s AND lifecycle='active'",(p.target.budget_id,)).fetchone()['n']==0
    assert fetched


@pytest.mark.parametrize('change',['maker','viewer','head','provider','hash','signature'])
def test_current_authority_or_identity_drift_cannot_approve(change,issuer_factory,https_signer):
    sign,_=https_signer;maker,checker,other,p,saved=prepared();issuer=BudgetCostIssuer(issuer_factory)
    actor=maker if change=='maker' else other if change=='viewer' else checker
    cmd=command(sign,actor,saved)
    if change=='hash':cmd.proposal_hash='f'*64
    if change=='signature':cmd.bearer_token=type(cmd.bearer_token)(sign(checker.subject,wrong_key=True))
    if change in {'head','provider'}:
        with isolated_owner() as conn:
            table,column,identity=('aip_budget_head','budget_id',p.target.budget_id) if change=='head' else ('aip_provider_instance_head','provider_instance_id',p.basis.provider.asset_id)
            conn.execute(sql.SQL('UPDATE {} SET current_revision=999 WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(column)),(identity,));conn.commit()
    with pytest.raises(BudgetCostIssuerBlocked):issuer.execute(cmd)
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_budget_cost_decision WHERE proposal_id=%s',(saved['proposalId'],)).fetchone()['n']==0


def test_original_hash_inquiry_conflict_and_current_member_required(issuer_factory,https_signer):
    sign,_=https_signer;_,checker,_,_,saved=prepared();issuer=BudgetCostIssuer(issuer_factory)
    cmd=command(sign,checker,saved)
    assert issuer.inquire(cmd)=={'status':'unresolved'}
    issuer.execute(cmd)
    changed=cmd.model_copy(update={'decision':'rejected'})
    assert issuer.inquire(changed)=={'status':'conflict'}
    with pytest.raises(BudgetCostIssuerBlocked):issuer.execute(changed)
    with connect(SCOPE) as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*SCOPE.key,checker.subject));conn.commit()
    with pytest.raises(BudgetCostIssuerBlocked):issuer.inquire(cmd)


def test_shared_database_login_cannot_issue_even_with_valid_jwt(https_signer):
    sign,_=https_signer;_,checker,_,_,saved=prepared()
    @contextmanager
    def wrong(scope,read_only):
        from aos_api.db import connect_serializable
        with connect_serializable(scope) as conn:yield conn
    with pytest.raises(BudgetCostIssuerBlocked,match='DATABASE_IDENTITY'):
        BudgetCostIssuer(wrong).execute(command(sign,checker,saved))


def test_runtime_sql_cannot_forge_approval(issuer_factory,https_signer):
    sign,_=https_signer;_,checker,_,_,saved=prepared();cmd=command(sign,checker,saved)
    BudgetCostIssuer(issuer_factory).execute(cmd)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect(SCOPE) as conn:
            conn.execute("INSERT INTO aip_budget_cost_issuer_receipt SELECT org_id,project_id,actor_subject,operation,'forged-'||idempotency_key,request_hash,result FROM aip_budget_cost_issuer_receipt WHERE idempotency_key=%s",(cmd.idempotency_key,))


def test_expiry_after_source_read_cannot_commit_approval(issuer_factory,https_signer,monkeypatch):
    import time
    from aos_api import aip_budget_cost_issuer as module
    sign,_=https_signer;_,checker,_,p,saved=prepared(window=1)
    original=module._provider
    def delayed(conn,scope,proposal):
        result=original(conn,scope,proposal)
        time.sleep(max(0,(p.target.effective_until-datetime.now(UTC)).total_seconds())+.02)
        return result
    monkeypatch.setattr(module,'_provider',delayed)
    with pytest.raises(BudgetCostIssuerBlocked,match='EXPIRED'):
        BudgetCostIssuer(issuer_factory).execute(command(sign,checker,saved))
    with connect(SCOPE) as conn:
        assert conn.execute('SELECT count(*) AS n FROM aip_budget_cost_decision WHERE proposal_id=%s',(saved['proposalId'],)).fetchone()['n']==0


def test_network_issuer_login_has_no_budget_signing_authority(private_passfile,https_signer):
    from tests.aip.test_network_issuer_timeouts_pg import live_issuer
    from aos_api.aip_network_issuer_connection import connect_issuer_decision
    sign,_=https_signer;_,checker,_,_,saved=prepared()
    with live_issuer(private_passfile) as config:
        @contextmanager
        def wrong(scope,read_only):
            with connect_issuer_decision(config,scope) as conn:yield conn
        with pytest.raises(BudgetCostIssuerBlocked,match='DATABASE_IDENTITY'):
            BudgetCostIssuer(wrong).execute(command(sign,checker,saved))


def test_receipt_insert_failure_rolls_back_signed_decision(issuer_factory,https_signer):
    sign,_=https_signer;_,checker,_,_,saved=prepared();cmd=command(sign,checker,saved)
    with isolated_owner() as conn:
        conn.execute("CREATE FUNCTION public.test_cost_issuer_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test-only receipt failure'; END $$")
        conn.execute('CREATE TRIGGER test_cost_issuer_failure BEFORE INSERT ON aip_budget_cost_issuer_receipt FOR EACH ROW EXECUTE FUNCTION public.test_cost_issuer_failure()');conn.commit()
    try:
        with pytest.raises(psycopg.Error):BudgetCostIssuer(issuer_factory).execute(cmd)
        with connect(SCOPE) as conn:
            assert conn.execute('SELECT count(*) AS n FROM aip_budget_cost_decision WHERE proposal_id=%s',(saved['proposalId'],)).fetchone()['n']==0
            assert conn.execute('SELECT count(*) AS n FROM aip_budget_cost_issuer_receipt WHERE idempotency_key=%s',(cmd.idempotency_key,)).fetchone()['n']==0
    finally:
        with isolated_owner() as conn:
            conn.execute('DROP TRIGGER test_cost_issuer_failure ON aip_budget_cost_issuer_receipt');conn.execute('DROP FUNCTION public.test_cost_issuer_failure()');conn.commit()


@pytest.mark.parametrize('table',['aip_budget_cost_decision','aip_budget_cost_revocation','aip_budget_cost_issuer_receipt'])
def test_review_tables_are_rls_immutable_and_runtime_insert_gated(table):
    with isolated_owner() as conn:
        row=conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()
        assert row=={'relrowsecurity':True,'relforcerowsecurity':True}
        with pytest.raises(psycopg.Error):conn.execute(sql.SQL('TRUNCATE {} CASCADE').format(sql.Identifier(table)))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect(SCOPE) as conn:
            conn.execute(sql.SQL('INSERT INTO {} (org_id,project_id) VALUES(%s,%s)').format(sql.Identifier(table)),SCOPE.key)
