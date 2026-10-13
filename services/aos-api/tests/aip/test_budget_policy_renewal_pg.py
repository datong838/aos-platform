"""Real isolated PG identity checks; publication/approval coverage is still pending.

The owned fixture uses local trust authentication and temporary LOGIN roles.
Passing here is not proof of production credential provisioning or a real human.
"""
import os

import psycopg
from psycopg import sql
import pytest

from aos_api.aip_budget_policy_renewal_identity import authenticate_machine_maker, RenewalIdentityBlocked


@pytest.fixture(scope='session')
def schema_database():
    dsn = os.environ.get('AOS_RENEWAL_SCHEMA_TEST_DSN')
    if not dsn:
        pytest.skip('owned isolated closed-schema fixture required')
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield dsn, conn


def test_native_candidate_roles_default_to_closed_without_membership(schema_database):
    _, admin = schema_database
    rows = admin.execute("""SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolbypassrls,
      rolcreatedb,rolcreaterole,rolreplication,
      EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid)
      FROM pg_roles r WHERE rolname LIKE 'aos_budget_renewal_%' ORDER BY rolname""").fetchall()
    assert len(rows) == 6
    assert all(not any(row[1:]) for row in rows)


def test_native_three_journals_are_forced_tenant_isolated_and_empty(schema_database):
    _, admin = schema_database
    for name in ('proposal', 'decision', 'receipt'):
        table = 'aip_budget_policy_renewal_' + name
        assert admin.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class '
                             'WHERE oid=%s::regclass', ('public.' + table,)).fetchone() == (True, True)
        assert admin.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table))).fetchone()[0] == 0
        triggers = admin.execute('SELECT tgname FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal',
                                  ('public.' + table,)).fetchall()
        expected={'renewal_immutable_update','renewal_immutable_truncate'}
        if name=='receipt':expected.add('renewal_consume_complete')
        assert {x[0] for x in triggers} == expected


def test_native_caller_permissions_only_include_bounded_checker_observation(schema_database):
    _, admin = schema_database
    for caller in ('maker', 'issuer', 'consumer'):
        role = 'aos_budget_renewal_' + caller + '_call'
        allowed = admin.execute('SELECT has_function_privilege(%s,%s,%s)',
                                (role, 'public.aip_renewal_checker_member_a0v_162()', 'EXECUTE')).fetchone()[0]
        assert allowed is (caller == 'issuer')
        for table in ('meta_membership', 'aip_model_governance_policy_head',
                      'aip_budget_policy_renewal_proposal', 'aip_budget_policy_renewal_decision',
                      'aip_budget_policy_renewal_receipt'):
            assert admin.execute('SELECT has_table_privilege(%s,%s,%s)',
                                  (role, 'public.' + table,
                                   'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')).fetchone()[0] is False


@pytest.fixture
def schema_issuer(schema_database):
    dsn, admin = schema_database
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    try:
        yield dsn, admin
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')


def checker_observation(dsn):
    with connect_actor(dsn, user='aos_budget_renewal_issuer_call') as conn:
        return conn.execute('SELECT public.aip_renewal_checker_member_a0v_162()').fetchone()[0]


def test_native_checker_observation_does_not_grant_direct_member_read(schema_issuer):
    dsn, _ = schema_issuer
    assert checker_observation(dsn) is False
    with connect_actor(dsn, user='aos_budget_renewal_issuer_call') as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('SELECT * FROM public.meta_membership')


def test_native_checker_read_only_observation_uses_current_fixture_member(schema_issuer):
    # This isolated catalog fixture is not a person, JWT or approval.
    dsn, admin = schema_issuer
    subject = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
    admin.execute('INSERT INTO public.meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)',
                  ('org-org', 'dev-project', subject, 'admin'))
    try:
        with psycopg.connect(dsn, user='aos_budget_renewal_issuer_call') as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute("SET LOCAL aos.org_id='org-org';SET LOCAL aos.project_id='dev-project'")
            assert conn.execute('SELECT public.aip_renewal_checker_member_a0v_162()').fetchone()[0] is True
        admin.execute('UPDATE public.meta_membership SET role=%s WHERE subject=%s', ('viewer', subject))
        assert checker_observation(dsn) is False
    finally:
        admin.execute('DELETE FROM public.meta_membership WHERE subject=%s', (subject,))


def test_native_owner_role_drift_blocks_observation(schema_issuer):
    dsn, admin = schema_issuer
    admin.execute('GRANT aos_runtime TO aos_budget_renewal_publish_owner')
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='ROLE_PROFILE_DRIFT'):
            checker_observation(dsn)
    finally:
        admin.execute('REVOKE aos_runtime FROM aos_budget_renewal_publish_owner')
    assert checker_observation(dsn) is False


def test_native_direct_caller_acl_drift_blocks_observation(schema_issuer):
    dsn, admin = schema_issuer
    admin.execute('GRANT SELECT ON public.meta_membership TO aos_budget_renewal_issuer_call')
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='RELATION_PROFILE_DRIFT'):
            checker_observation(dsn)
    finally:
        admin.execute('REVOKE SELECT ON public.meta_membership FROM aos_budget_renewal_issuer_call')
    assert checker_observation(dsn) is False


def test_native_disabled_commit_guard_blocks_even_checker_observation(schema_issuer):
    dsn,admin=schema_issuer
    admin.execute('ALTER TABLE public.aip_budget_policy_renewal_receipt DISABLE TRIGGER renewal_consume_complete')
    try:
        with pytest.raises(psycopg.errors.InsufficientPrivilege,match='COMPLETENESS_TRIGGER_DRIFT'):
            checker_observation(dsn)
    finally:
        admin.execute('ALTER TABLE public.aip_budget_policy_renewal_receipt ENABLE TRIGGER renewal_consume_complete')
    assert checker_observation(dsn) is False


def test_native_store_rejects_nested_or_autocommit_connection(schema_issuer):
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    dsn, _ = schema_issuer
    with connect_actor(dsn, user='aos_budget_renewal_issuer_call') as conn:
        with pytest.raises(RenewalStoreBlocked, match='REAL_IDLE_DATABASE_CONNECTION'):
            RenewalAuthorityStore(conn)
    with psycopg.connect(dsn, user='aos_budget_renewal_issuer_call', autocommit=True) as conn:
        with pytest.raises(RenewalStoreBlocked, match='REAL_IDLE_DATABASE_CONNECTION'):
            RenewalAuthorityStore(conn)


def test_native_store_independently_blocks_modified_checker_function_body(schema_issuer):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    from pydantic import SecretStr
    dsn, admin = schema_issuer
    original = admin.execute("SELECT pg_get_functiondef('public.aip_renewal_checker_member_a0v_162()'::regprocedure)").fetchone()[0]
    admin.execute('''CREATE OR REPLACE FUNCTION public.aip_renewal_checker_member_a0v_162()
        RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog
        AS $$ BEGIN RETURN true; END $$''')
    command = RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-decision',proposalId='fixture-proposal',proposalHash='a'*64,
        targetActiveHash='b'*64,decision='approved')
    try:
        with psycopg.connect(dsn, user='aos_budget_renewal_issuer_call') as conn:
            with pytest.raises(RenewalStoreBlocked, match='SCHEMA_SEAL_DRIFT'):
                RenewalAuthorityStore(conn).decide(command, token=SecretStr('not-a-jwt'))
    finally:
        admin.execute(original)
    assert checker_observation(dsn) is False


@pytest.fixture(scope='session')
def schema_source(schema_database):
    """Isolated canonical test data only; never an approval or real customer read."""
    from datetime import UTC, datetime, timedelta
    from aos_api.aip_budget_contracts import BudgetRevisionCreate
    from aos_api.aip_budget_store import materialize_revision
    from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate
    from aos_api.aip_model_governance_policy_store import materialize_policy, canonical_hash
    from aos_api.tenant_scope import TenantScope
    from psycopg.types.json import Jsonb
    dsn, admin = schema_database
    now = datetime.now(UTC).replace(microsecond=0)
    scope = TenantScope('org-org', 'dev-project')
    budget = materialize_revision(scope, 'fixture-schema-setup', BudgetRevisionCreate(
        budgetId='fixture-budget', revision=1, lifecycle='active', dailyLimitMinor=100,
        monthlyLimitMinor=1000, alertThresholdPct=80, owner='fixture-owner',
        overBudgetApprover='fixture-reviewer', effectiveFrom=now-timedelta(days=30),
        effectiveUntil=now+timedelta(days=365)), created_at=now)
    ref = lambda kind, identifier, digest: dict(assetType=kind,assetId=identifier,revision=1,contentHash=digest)
    provider = dict(tenant=dict(orgId='org-org',projectId='dev-project'),
        providerInstanceId='fixture-provider', revision=1, lifecycle='active',
        pluginRef=ref('ProviderPluginRevision','fixture-plugin','a'*64),
        endpointProfile=dict(baseUrl='https://provider.invalid',region='fixture',timeoutMs=1000,metadata={}),
        secretRef='vault://fixture/provider',secretVersion='fixture-only',
        egressPolicyRef=ref('EgressPolicyRevision','fixture-egress','b'*64),
        dataClassificationPolicyRef=ref('DataClassificationPolicyRevision','fixture-classification','c'*64),
        createdBy='fixture-schema-setup',createdAt=now.isoformat())
    provider['contentHash']=canonical_hash({k:v for k,v in provider.items()
        if k not in {'tenant','revision','createdBy','createdAt'}})
    budget_ref=ref('BudgetRevision','fixture-budget',budget.content_hash)
    provider_ref=ref('ProviderInstanceRevision','fixture-provider',provider['contentHash'])
    source=materialize_policy(scope,'fixture-schema-setup',BudgetPolicyRevisionCreate(
        policyId='fixture-expired-policy',revision=13,owner='fixture-owner',lifecycle='active',
        effectiveFrom=now-timedelta(days=2),effectiveUntil=now-timedelta(days=1),
        approvalRef='fixture-historical-approval-not-real',budgetRevisionRef=budget_ref,
        developmentCostAuthorization=dict(tenant=provider['tenant'],provider=provider_ref,
            providerModelId='fixture-model',environment='development',
            approvalRef='fixture-historical-approval-not-real',
            effectiveFrom=now-timedelta(days=3),effectiveUntil=now-timedelta(hours=12))),created_at=now)
    with admin.transaction():
        admin.execute("INSERT INTO public.aip_budget_head(org_id,project_id,budget_id,current_revision) VALUES('org-org','dev-project','fixture-budget',1)")
        admin.execute('''INSERT INTO public.aip_budget_revision(org_id,project_id,budget_id,revision,content_hash,
          lifecycle,environment,currency,daily_limit_minor,monthly_limit_minor,alert_threshold_pct,hard_stop,
          unknown_usage_behavior,effective_from,effective_until,owner,over_budget_approver,payload,created_by,created_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
          (*scope.key,budget.budget_id,budget.revision,budget.content_hash,'active','development','CNY',
           100,1000,80,True,'block',budget.effective_from,budget.effective_until,budget.owner,
           budget.over_budget_approver,Jsonb(budget.model_dump(mode='json',by_alias=True)),budget.created_by,now))
        admin.execute("INSERT INTO public.aip_provider_instance_head(org_id,project_id,provider_instance_id,current_revision) VALUES('org-org','dev-project','fixture-provider',1)")
        admin.execute('INSERT INTO public.aip_provider_instance_revision VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                      (*scope.key,'fixture-provider',1,provider['contentHash'],'active',Jsonb(provider),'fixture-schema-setup',now))
        admin.execute("INSERT INTO public.aip_model_governance_policy_head VALUES('org-org','dev-project','budget','fixture-expired-policy',13,13,%s)",(now,))
        admin.execute('INSERT INTO public.aip_model_governance_policy_revision VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
          (*scope.key,'budget',source.policy_id,13,source.content_hash,'active',source.effective_from,
           source.effective_until,Jsonb(source.model_dump(mode='json',by_alias=True)),source.created_by,now))
        admin.execute("INSERT INTO public.meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','6f31cfdc-a26c-4f1f-ad6b-95a8559cc657','admin')")
    admin.execute('ALTER ROLE aos_budget_renewal_maker_call LOGIN')
    try:
        yield dsn,admin,source,now
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_maker_call NOLOGIN')
        # Fixture journals are immutable: retain them until owned tmpfs teardown.
        # A new fixture database is required for any fresh full-suite repetition.


def test_native_machine_proposal_uses_original_facts_without_financial_publication(schema_source):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore
    from datetime import timedelta
    dsn,admin,source,now=schema_source
    command=RenewalProposalCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-propose-1',sourcePolicyId=source.policy_id,
        expectedSourceRevision=13,expectedHeadVersion=13,expectedSourceHash=source.content_hash,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=30))
    with psycopg.connect(dsn,user='aos_budget_renewal_maker_call') as conn:
        store=RenewalAuthorityStore(conn)
        result=store.propose(command)
        assert result['status']=='prepared' and result['activationEligible'] is False
        assert result['proposal']['makerSubject']=='postgres-service:aos_budget_renewal_maker_call'
        assert result['targetDraft']['lifecycle']=='draft' and result['targetDraft']['revision']==14
        assert result['targetDraft']['owner']==source.owner
        assert result['targetDraft']['approvalRef']!=source.approval_ref
        assert store.propose(command)==result
        observed=store.reconcile(command)
        assert observed['status']=='observed' and observed['proposalHash']==result['proposalHash']
        # Historical reconciliation must not claim fresh current-head admission.
        admin.execute("UPDATE public.aip_model_governance_policy_head SET current_revision=99,version=14")
        try:
            assert store.reconcile(command)['proposalHash']==result['proposalHash']
        finally:
            admin.execute("UPDATE public.aip_model_governance_policy_head SET current_revision=13,version=13")
        wrong=command.model_copy(update={'effective_until':now+timedelta(minutes=31)})
        assert store.reconcile(wrong)['status']=='conflict'
        from aos_api.aip_budget_policy_renewal_store import RenewalStoreBlocked
        with pytest.raises(RenewalStoreBlocked,match='23514'):
            store.propose(wrong)
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(13,13)
    assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision').fetchone()[0]==1
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]==1
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_decision').fetchone()[0]==0
    assert admin.execute('SELECT operation FROM public.aip_budget_policy_renewal_receipt').fetchall()==[('propose',)]


@pytest.mark.parametrize('change', ['head', 'budget', 'provider', 'checker'])
def test_native_new_proposal_rechecks_current_dependencies_and_rolls_back(schema_source,change):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    from datetime import timedelta
    dsn,admin,source,now=schema_source
    before=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]
    command=RenewalProposalCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-negative-'+change,sourcePolicyId=source.policy_id,
        expectedSourceRevision=13,expectedHeadVersion=13,expectedSourceHash=source.content_hash,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=30))
    mutate,restore={
        'head':("UPDATE public.aip_model_governance_policy_head SET version=14",
                "UPDATE public.aip_model_governance_policy_head SET version=13"),
        'budget':("UPDATE public.aip_budget_head SET current_revision=2",
                  "UPDATE public.aip_budget_head SET current_revision=1"),
        'provider':("UPDATE public.aip_provider_instance_head SET current_revision=2",
                    "UPDATE public.aip_provider_instance_head SET current_revision=1"),
        'checker':("UPDATE public.meta_membership SET role='viewer'",
                   "UPDATE public.meta_membership SET role='admin'"),
    }[change]
    admin.execute(mutate)
    try:
        with psycopg.connect(dsn,user='aos_budget_renewal_maker_call') as conn:
            with pytest.raises(RenewalStoreBlocked):
                RenewalAuthorityStore(conn).propose(command)
    finally:
        admin.execute(restore)
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]==before
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_receipt').fetchone()[0]==before


@pytest.mark.parametrize('field,value', [('makerSubject','pretend'),('schemaVersion',1.0),
    ('idempotencyKey',123),('orgId','dev-org'),('effectiveFrom','2026-10-14T00:00:00')])
def test_native_sql_proposal_rejects_raw_untyped_or_injected_request(schema_source,field,value):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand
    from psycopg.types.json import Jsonb
    from datetime import timedelta
    dsn,admin,source,now=schema_source
    c=RenewalProposalCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-raw-'+field,sourcePolicyId=source.policy_id,
        expectedSourceRevision=13,expectedHeadVersion=13,expectedSourceHash=source.content_hash,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=30)).canonical_payload()
    c[field]=value
    before=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]
    with connect_actor(dsn,user='aos_budget_renewal_maker_call') as conn:
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            conn.execute('SELECT public.aip_renewal_propose_a0v_162(%s)',(Jsonb(c),))
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_proposal').fetchone()[0]==before


@pytest.mark.parametrize('bad', ['actor','target','injected','maker'])
def test_native_issuer_rejects_wrong_identity_target_and_raw_fields(schema_source,bad):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand
    from aos_api.aip_model_governance_policy_store import canonical_hash
    from psycopg.types.json import Jsonb
    dsn,admin,_,_=schema_source
    p=admin.execute('SELECT proposal_id,proposal_hash,payload FROM public.aip_budget_policy_renewal_proposal').fetchone()
    command=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-invalid-issuer-'+bad,proposalId=p[0],proposalHash=p[1],
        targetActiveHash=canonical_hash(p[2]['targetActive']),decision='approved').canonical_payload()
    actor='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
    if bad=='actor':actor='pretend-other-reviewer'
    if bad=='target':command['targetActiveHash']='e'*64
    if bad=='injected':command['actorSubject']=actor
    before=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_decision').fetchone()[0]
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    try:
        user='aos_budget_renewal_maker_call' if bad=='maker' else 'aos_budget_renewal_issuer_call'
        with connect_actor(dsn,user=user) as conn:
            with pytest.raises(psycopg.Error):
                conn.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',(Jsonb(command),actor))
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_decision').fetchone()[0]==before


def test_native_issuer_fixture_decision_and_revocation_are_atomic_without_publication(schema_source):
    """Database TCB fixture only: no JWT, real person, consent or original approval."""
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand, RenewalRevocationCommand
    from psycopg.types.json import Jsonb
    dsn,admin,source,now=schema_source
    p=admin.execute('SELECT proposal_id,proposal_hash,payload FROM public.aip_budget_policy_renewal_proposal').fetchone()
    from aos_api.aip_model_governance_policy_store import canonical_hash
    command=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-issuer-decision',proposalId=p[0],proposalHash=p[1],
        targetActiveHash=canonical_hash(p[2]['targetActive']),decision='approved')
    actor='6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    try:
        with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as conn:
            result=conn.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',
                                (Jsonb(command.canonical_payload()),actor)).fetchone()[0]
        assert result['status']=='decided' and result['activationEligible'] is False
        with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as conn:
            assert conn.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',
                (Jsonb(command.canonical_payload()),actor)).fetchone()[0]==result
        revoke=RenewalRevocationCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
            idempotencyKey='fixture-issuer-revoke',proposalId=p[0],proposalHash=p[1],
            decisionId=result['decisionId'],decisionHash=result['decisionHash'],reasonCode='approval_withdrawn')
        # Unsafe current Provider drift must not prevent withdrawing an approval.
        admin.execute('UPDATE public.aip_provider_instance_head SET current_revision=2')
        try:
            with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as conn:
                withdrawn=conn.execute('SELECT public.aip_renewal_revoke_a0v_162(%s,%s)',
                    (Jsonb(revoke.canonical_payload()),actor)).fetchone()[0]
            assert withdrawn['status']=='revoked' and withdrawn['activationEligible'] is False
        finally:
            admin.execute('UPDATE public.aip_provider_instance_head SET current_revision=1')
        with psycopg.connect(dsn,user='aos_budget_renewal_issuer_call') as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute("SET LOCAL aos.org_id='org-org';SET LOCAL aos.project_id='dev-project'")
            observed=conn.execute('SELECT public.aip_renewal_reconcile_a0v_162(%s,%s,%s)',
                (Jsonb(command.canonical_payload()),'decide',actor)).fetchone()[0]
            assert observed['status']=='observed' and observed['decisionHash']==result['decisionHash']
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')
    assert admin.execute('SELECT decision FROM public.aip_budget_policy_renewal_decision ORDER BY created_at').fetchall()==[('approved',),('revoked',)]
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(13,13)
    assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision').fetchone()[0]==1


def test_native_private_store_rejects_fake_jwt_even_for_real_issuer_login(schema_source,monkeypatch):
    from aos_api.aip_budget_policy_renewal_contracts import RenewalDecisionCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore
    from aos_api.aip_budget_policy_renewal_identity import CheckerBinding, RenewalIdentityBlocked
    from test_budget_policy_renewal_identity import protected_environment
    from pydantic import SecretStr
    dsn,admin,_,_=schema_source
    p=admin.execute('SELECT proposal_id,proposal_hash FROM public.aip_budget_policy_renewal_proposal').fetchone()
    command=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-invalid-jwt',proposalId=p[0],proposalHash=p[1],targetActiveHash='a'*64,decision='approved')
    env=protected_environment()
    for key,value in env.items():monkeypatch.setenv(key,value)
    binding=CheckerBinding('6f31cfdc-a26c-4f1f-ad6b-95a8559cc657','a'*64,tuple(env.items()))
    before=admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_decision').fetchone()[0]
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    try:
        with psycopg.connect(dsn,user='aos_budget_renewal_issuer_call') as conn:
            with pytest.raises(RenewalIdentityBlocked,match='ORIGINAL_HUMAN_IDENTITY_REQUIRED'):
                RenewalAuthorityStore(conn,checker_binding=binding).decide(command,token=SecretStr('not-a-jwt'))
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')
    assert admin.execute('SELECT count(*) FROM public.aip_budget_policy_renewal_decision').fetchone()[0]==before


def test_native_three_role_consumer_publishes_canonical_policy_and_reconciles_history(schema_source):
    """Owned DB issuer TCB test only; not real human consent or production activation."""
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand, RenewalDecisionCommand, RenewalConsumeCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore
    from psycopg.types.json import Jsonb
    from datetime import timedelta
    dsn,admin,source,now=schema_source
    # The original canonical trigger is installed after schema-admin fixture seeding.
    admin.execute('CREATE TRIGGER cost_configuration_write_guard BEFORE INSERT ON public.aip_model_governance_policy_revision '
                  'FOR EACH ROW EXECUTE FUNCTION public.aip_cost_configuration_write_guard_a0v_128()')
    pcommand=RenewalProposalCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-consume-propose',sourcePolicyId=source.policy_id,
        expectedSourceRevision=13,expectedHeadVersion=13,expectedSourceHash=source.content_hash,
        effectiveFrom=now-timedelta(minutes=1),effectiveUntil=now+timedelta(minutes=30))
    with psycopg.connect(dsn,user='aos_budget_renewal_maker_call') as conn:
        proposal=RenewalAuthorityStore(conn).propose(pcommand)
    dcommand=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='fixture-consume-decision',proposalId=proposal['proposalId'],
        proposalHash=proposal['proposalHash'],targetActiveHash=proposal['targetActiveHash'],decision='approved')
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    admin.execute('ALTER ROLE aos_budget_renewal_consumer_call LOGIN')
    try:
        with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as conn:
            decision=conn.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',
                (Jsonb(dcommand.canonical_payload()),'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()[0]
        command=RenewalConsumeCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
            idempotencyKey='fixture-consume',proposalId=proposal['proposalId'],proposalHash=proposal['proposalHash'],
            decisionId=decision['decisionId'],decisionHash=decision['decisionHash'])
        # Force expiration after the SQL function returns but before COMMIT.
        # An uncommitted observed DTO must never be accepted as published proof.
        from datetime import datetime,UTC
        import time
        # The database owns expiration; a VM clock may differ from the host.
        clock=admin.execute('SELECT clock_timestamp()').fetchone()[0]
        short=pcommand.model_copy(update={'idempotency_key':'fixture-short-propose',
            'effective_from':clock-timedelta(seconds=1),'effective_until':clock+timedelta(seconds=2)})
        with psycopg.connect(dsn,user='aos_budget_renewal_maker_call') as conn:
            short_p=RenewalAuthorityStore(conn).propose(short)
        short_dc=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
            idempotencyKey='fixture-short-decision',proposalId=short_p['proposalId'],
            proposalHash=short_p['proposalHash'],targetActiveHash=short_p['targetActiveHash'],decision='approved')
        with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as conn:
            short_d=conn.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',
                (Jsonb(short_dc.canonical_payload()),'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()[0]
        short_c=RenewalConsumeCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
            idempotencyKey='fixture-short-consume',proposalId=short_p['proposalId'],proposalHash=short_p['proposalHash'],
            decisionId=short_d['decisionId'],decisionHash=short_d['decisionHash'])
        with pytest.raises(psycopg.errors.CheckViolation,match='INCOMPLETE_OR_EXPIRED_PUBLICATION'):
            with connect_actor(dsn,user='aos_budget_renewal_consumer_call') as conn:
                pending=conn.execute('SELECT public.aip_renewal_consume_a0v_162(%s)',
                    (Jsonb(short_c.canonical_payload()),)).fetchone()[0]
                assert pending['status']=='observed'
                assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision WHERE revision=14').fetchone()[0]==0
                # Bound observation, not authorization. Colima may correct its
                # wall clock while running; the actual 2s DB window is unchanged.
                until=time.monotonic()+10
                while admin.execute('SELECT clock_timestamp()').fetchone()[0]<short.effective_until:
                    assert time.monotonic()<until, 'database expiration not observed'
                    time.sleep(.01)
        assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(13,13)
        assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume'").fetchone()[0]==0
        with psycopg.connect(dsn,user='aos_budget_renewal_consumer_call') as conn:
            store=RenewalAuthorityStore(conn)
            # Native fault injection: suppress the actual head UPDATE after the
            # original canonical INSERT, then prove the entire transaction rolls back.
            admin.execute('''CREATE FUNCTION public.fixture_cas_miss() RETURNS trigger LANGUAGE plpgsql
                AS $$ BEGIN RETURN NULL; END $$''')
            admin.execute('CREATE TRIGGER fixture_cas_miss BEFORE UPDATE ON public.aip_model_governance_policy_head '
                          'FOR EACH ROW EXECUTE FUNCTION public.fixture_cas_miss()')
            from aos_api.aip_budget_policy_renewal_store import RenewalStoreBlocked
            try:
                with pytest.raises(RenewalStoreBlocked,match='23514'):
                    store.consume(command)
            finally:
                admin.execute('DROP TRIGGER fixture_cas_miss ON public.aip_model_governance_policy_head')
                admin.execute('DROP FUNCTION public.fixture_cas_miss()')
            assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(13,13)
            assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision WHERE revision=14').fetchone()[0]==0
            assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume'").fetchone()[0]==0
            result=store.consume(command)
            assert result['status']=='observed' and result['activationEligible'] is False
            assert result['ref']['assetType']=='BudgetPolicyRevision' and result['ref']['revision']==14
            assert store.consume(command)==result
            assert store.reconcile(command)['ref']==result['ref']
            old=admin.execute("SELECT d.proposal_id,p.proposal_hash,d.decision_id,d.decision_hash "
                "FROM public.aip_budget_policy_renewal_decision d JOIN public.aip_budget_policy_renewal_proposal p "
                "USING(org_id,project_id,proposal_id) WHERE d.decision='approved' AND d.proposal_id<>%s "
                "AND EXISTS(SELECT 1 FROM public.aip_budget_policy_renewal_decision x WHERE x.proposal_id=d.proposal_id AND x.decision='revoked')",
                (proposal['proposalId'],)).fetchone()
            if old:
                revoked=RenewalConsumeCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
                    idempotencyKey='fixture-revoked-consume',proposalId=old[0],proposalHash=old[1],
                    decisionId=old[2],decisionHash=old[3])
                with pytest.raises(RenewalStoreBlocked,match='42501'):
                    store.consume(revoked)
            admin.execute('UPDATE public.aip_model_governance_policy_head SET current_revision=99,version=15')
            try:assert store.reconcile(command)['ref']==result['ref']
            finally:admin.execute('UPDATE public.aip_model_governance_policy_head SET current_revision=14,version=14')
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')
        admin.execute('ALTER ROLE aos_budget_renewal_consumer_call NOLOGIN')
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head').fetchone()==(14,14)
    assert admin.execute("SELECT count(*) FROM public.aip_model_governance_policy_revision WHERE revision=14 AND lifecycle='active'").fetchone()[0]==1
    assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume'").fetchone()[0]==1


def race_proposal(schema_source,tag,source_policy=None):
    """Fixture-only canonical setup; all actual race operations use low roles."""
    from aos_api.aip_model_governance_policy_contracts import BudgetPolicyRevisionCreate
    from aos_api.aip_model_governance_policy_store import materialize_policy
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_budget_policy_renewal_contracts import RenewalProposalCommand, RenewalDecisionCommand, RenewalConsumeCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore
    from psycopg.types.json import Jsonb
    from datetime import datetime,UTC,timedelta
    dsn,admin,source,_=schema_source
    now=admin.execute('SELECT clock_timestamp()').fetchone()[0]
    source=source_policy or source
    raw=source.model_dump(mode='json',by_alias=True)
    body={k:v for k,v in raw.items() if k not in {'tenant','contentHash','createdBy','createdAt'}}
    body['policyId']=source.policy_id if source_policy else 'fixture-race-'+tag
    clone=materialize_policy(TenantScope('org-org','dev-project'),'fixture-schema-setup',
                             BudgetPolicyRevisionCreate.model_validate(body),created_at=now)
    # Explicit setup only. Restore the original trigger before any normal actor.
    if source_policy is None:
        with admin.transaction():
            _seed_race_source(admin,clone,now,Jsonb)
    else:
        clone=source_policy
    command=RenewalProposalCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='race-propose-'+tag,sourcePolicyId=clone.policy_id,
        expectedSourceRevision=13,expectedHeadVersion=13,expectedSourceHash=clone.content_hash,
        effectiveFrom=now-timedelta(seconds=1),effectiveUntil=now+timedelta(minutes=30))
    with psycopg.connect(dsn,user='aos_budget_renewal_maker_call') as c:
        p=RenewalAuthorityStore(c).propose(command)
    dc=RenewalDecisionCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='race-decide-'+tag,proposalId=p['proposalId'],proposalHash=p['proposalHash'],
        targetActiveHash=p['targetActiveHash'],decision='approved')
    with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as c:
        d=c.execute('SELECT public.aip_renewal_decide_a0v_162(%s,%s)',
                    (Jsonb(dc.canonical_payload()),'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()[0]
    cc=RenewalConsumeCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='race-consume-'+tag,proposalId=p['proposalId'],proposalHash=p['proposalHash'],
        decisionId=d['decisionId'],decisionHash=d['decisionHash'])
    return clone,cc,p


def _seed_race_source(admin,clone,now,Jsonb):
        # Only called inside the explicit schema-admin setup transaction.
        admin.execute('ALTER TABLE public.aip_model_governance_policy_revision DISABLE TRIGGER cost_configuration_write_guard')
        admin.execute('INSERT INTO public.aip_model_governance_policy_head VALUES(%s,%s,%s,%s,%s,%s,%s)',
                      ('org-org','dev-project','budget',clone.policy_id,13,13,now))
        admin.execute('INSERT INTO public.aip_model_governance_policy_revision VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                      ('org-org','dev-project','budget',clone.policy_id,13,clone.content_hash,'active',
                       clone.effective_from,clone.effective_until,Jsonb(clone.model_dump(mode='json',by_alias=True)),clone.created_by,now))
        admin.execute('SET CONSTRAINTS ALL IMMEDIATE')
        admin.execute('ALTER TABLE public.aip_model_governance_policy_revision ENABLE TRIGGER cost_configuration_write_guard')


def wait_native_lock(admin,pid,event=None):
    import time
    until=time.monotonic()+2
    while time.monotonic()<until:
        row=admin.execute('SELECT wait_event_type,wait_event FROM pg_stat_activity WHERE pid=%s',(pid,)).fetchone()
        if row and row[0]=='Lock' and (event is None or row[1]==event):return row
        time.sleep(.01)
    raise AssertionError('actual native lock wait not observed')


@pytest.fixture
def race_roles(schema_source):
    dsn,admin,_,_=schema_source
    admin.execute('ALTER ROLE aos_budget_renewal_issuer_call LOGIN')
    admin.execute('ALTER ROLE aos_budget_renewal_consumer_call LOGIN')
    try:yield schema_source
    finally:
        admin.execute('ALTER ROLE aos_budget_renewal_issuer_call NOLOGIN')
        admin.execute('ALTER ROLE aos_budget_renewal_consumer_call NOLOGIN')


@pytest.mark.parametrize('first',['revoke','consume'])
def test_native_revocation_consumer_order_is_serialized_by_actual_lock(race_roles,first):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from aos_api.aip_budget_policy_renewal_contracts import RenewalRevocationCommand
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    from psycopg.types.json import Jsonb
    dsn,admin,_,_=race_roles
    source,command,_=race_proposal(race_roles,'order-'+first)
    revoke=RenewalRevocationCommand(schemaVersion=1,orgId='org-org',projectId='dev-project',
        idempotencyKey='race-revoke-'+first,proposalId=command.proposal_id,proposalHash=command.proposal_hash,
        decisionId=command.decision_id,decisionHash=command.decision_hash,reasonCode='approval_withdrawn')
    ids=Queue()
    def work():
        if first=='revoke':
            with psycopg.connect(dsn,user='aos_budget_renewal_consumer_call') as c:
                ids.put(c.info.backend_pid)
                try:return RenewalAuthorityStore(c).consume(command)
                except RenewalStoreBlocked as e:return str(e)
        with connect_actor(dsn,user='aos_budget_renewal_issuer_call') as c:
            c.execute("SET LOCAL lock_timeout='2000';SET LOCAL statement_timeout='5000'")
            ids.put(c.info.backend_pid)
            return c.execute('SELECT public.aip_renewal_revoke_a0v_162(%s,%s)',
                (Jsonb(revoke.canonical_payload()),'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657')).fetchone()[0]
    holder=connect_actor(dsn,user='aos_budget_renewal_issuer_call' if first=='revoke' else 'aos_budget_renewal_consumer_call')
    try:
        if first=='revoke':holder.execute('SELECT public.aip_renewal_revoke_a0v_162(%s,%s)',
            (Jsonb(revoke.canonical_payload()),'6f31cfdc-a26c-4f1f-ad6b-95a8559cc657'))
        else:holder.execute('SELECT public.aip_renewal_consume_a0v_162(%s)',(Jsonb(command.canonical_payload()),))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(work)
            wait_native_lock(admin,ids.get(timeout=2),'advisory')
            holder.commit()
            result=future.result(timeout=5)
        if first=='revoke':assert '42501' in result
        else:assert result['status']=='revoked'
    finally:
        holder.rollback();holder.close()
    head=admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head WHERE policy_id=%s',
                       (source.policy_id,)).fetchone()
    assert head==((13,13) if first=='revoke' else (14,14))
    count=admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id=%s",
                       (command.proposal_id,)).fetchone()[0]
    assert count==(0 if first=='revoke' else 1)


def test_native_same_source_two_approved_proposals_allow_one_publication(race_roles):
    from concurrent.futures import ThreadPoolExecutor
    from queue import Queue
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore, RenewalStoreBlocked
    dsn,admin,_,_=race_roles
    source,first,_=race_proposal(race_roles,'cas-first')
    _,second,_=race_proposal(race_roles,'cas-second',source_policy=source)
    ids=Queue()
    def other():
        with psycopg.connect(dsn,user='aos_budget_renewal_consumer_call') as c:
            ids.put(c.info.backend_pid)
            try:return RenewalAuthorityStore(c).consume(second)
            except RenewalStoreBlocked as e:return str(e)
    holder=connect_actor(dsn,user='aos_budget_renewal_consumer_call')
    try:
        pending=holder.execute('SELECT public.aip_renewal_consume_a0v_162(%s)',
                               (Jsonb(first.canonical_payload()),)).fetchone()[0]
        assert pending['status']=='observed'
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(other)
            wait_native_lock(admin,ids.get(timeout=2),'transactionid')
            holder.commit()
            assert '23514' in future.result(timeout=5)
    finally:
        holder.rollback();holder.close()
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head WHERE policy_id=%s',
                         (source.policy_id,)).fetchone()==(14,14)
    assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision WHERE policy_id=%s AND revision=14',
                         (source.policy_id,)).fetchone()[0]==1
    counts=admin.execute("SELECT proposal_id,count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id IN(%s,%s) GROUP BY proposal_id",
                         (first.proposal_id,second.proposal_id)).fetchall()
    assert counts==[(first.proposal_id,1)]


def test_native_receipt_only_fault_cannot_commit_half_publication(race_roles):
    from psycopg.types.json import Jsonb
    dsn,admin,_,_=race_roles
    source,command,_=race_proposal(race_roles,'receipt-only')
    # Schema-admin fault injection only. Normal consumer still traverses the
    # original insert guard, writes its proper same-tx Receipt, and executes CAS.
    admin.execute("CREATE FUNCTION public.fixture_drop_policy_r19() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NULL; END $$")
    admin.execute("CREATE FUNCTION public.fixture_keep_head_r19() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN OLD; END $$")
    admin.execute('CREATE TRIGGER zz_fixture_drop_policy BEFORE INSERT ON public.aip_model_governance_policy_revision FOR EACH ROW EXECUTE FUNCTION public.fixture_drop_policy_r19()')
    admin.execute('CREATE TRIGGER zz_fixture_keep_head BEFORE UPDATE ON public.aip_model_governance_policy_head FOR EACH ROW EXECUTE FUNCTION public.fixture_keep_head_r19()')
    try:
        with pytest.raises(psycopg.errors.NoDataFound):
            with connect_actor(dsn,user='aos_budget_renewal_consumer_call') as c:
                result=c.execute('SELECT public.aip_renewal_consume_a0v_162(%s)',
                                 (Jsonb(command.canonical_payload()),)).fetchone()[0]
                assert result['status']=='observed'  # Still uncommitted, not proof.
                assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id=%s",
                                     (command.proposal_id,)).fetchone()[0]==0
    finally:
        admin.execute('DROP TRIGGER zz_fixture_drop_policy ON public.aip_model_governance_policy_revision')
        admin.execute('DROP TRIGGER zz_fixture_keep_head ON public.aip_model_governance_policy_head')
        admin.execute('DROP FUNCTION public.fixture_drop_policy_r19()')
        admin.execute('DROP FUNCTION public.fixture_keep_head_r19()')
    assert admin.execute('SELECT current_revision,version FROM public.aip_model_governance_policy_head WHERE policy_id=%s',
                         (source.policy_id,)).fetchone()==(13,13)
    assert admin.execute('SELECT count(*) FROM public.aip_model_governance_policy_revision WHERE policy_id=%s AND revision=14',
                         (source.policy_id,)).fetchone()[0]==0
    assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id=%s",
                         (command.proposal_id,)).fetchone()[0]==0


def test_native_commit_ack_discarded_is_resolved_only_by_readonly_history(race_roles):
    import time
    from psycopg.types.json import Jsonb
    from aos_api.aip_budget_policy_renewal_store import RenewalAuthorityStore
    dsn,admin,_,_=race_roles
    source,command,_=race_proposal(race_roles,'lost-ack')
    c=connect_actor(dsn,user='aos_budget_renewal_consumer_call')
    try:
        assert c.execute('SELECT public.aip_renewal_consume_a0v_162(%s)',
                         (Jsonb(command.canonical_payload()),)).fetchone()[0]['status']=='observed'
        # libpq sends COMMIT but intentionally never reads its result/ack.
        c.pgconn.send_query(b'COMMIT')
        assert c.pgconn.flush()==0
        until=time.monotonic()+2
        while time.monotonic()<until:
            row=admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id=%s",
                              (command.proposal_id,)).fetchone()[0]
            if row==1:break
            time.sleep(.01)
        else:raise AssertionError('server commit not independently observed')
    finally:c.close()
    with psycopg.connect(dsn,user='aos_budget_renewal_consumer_call') as reader:
        result=RenewalAuthorityStore(reader).reconcile(command)
        assert result['status']=='observed' and result['ref']['revision']==14
    assert admin.execute("SELECT count(*) FROM public.aip_budget_policy_renewal_receipt WHERE operation='consume' AND proposal_id=%s",
                         (command.proposal_id,)).fetchone()[0]==1


@pytest.fixture
def identity_database():
    dsn = os.environ.get('AOS_RENEWAL_IDENTITY_TEST_DSN')
    if not dsn:
        pytest.skip('owned isolated identity PG fixture required')
    with psycopg.connect(dsn, autocommit=True) as admin:
        yield dsn, admin


def connect_actor(dsn, *, user='aos_budget_renewal_maker_call', org='org-org', project='dev-project'):
    conn = psycopg.connect(dsn, user=user)
    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", (org, project))
    return conn


def test_real_low_privilege_session_derives_machine_subject(identity_database):
    dsn, _ = identity_database
    with connect_actor(dsn) as conn:
        actual = authenticate_machine_maker(conn)
        assert actual.subject == 'postgres-service:aos_budget_renewal_maker_call'
        assert actual.session_user == 'aos_budget_renewal_maker_call'
        assert actual.activation_eligible is False


@pytest.mark.parametrize('changes', [dict(user='postgres'), dict(user='aos_budget_renewal_issuer_call'),
                                   dict(org='dev-org'), dict(project='other')])
def test_native_wrong_session_or_tenant_is_denied(identity_database, changes):
    dsn, _ = identity_database
    with connect_actor(dsn, **changes) as conn:
        with pytest.raises(RenewalIdentityBlocked):
            authenticate_machine_maker(conn)


def test_set_role_cannot_impersonate_authenticated_login(identity_database):
    dsn, _ = identity_database
    with connect_actor(dsn, user='postgres') as conn:
        conn.execute('SET LOCAL ROLE aos_budget_renewal_maker_call')
        with pytest.raises(RenewalIdentityBlocked):
            authenticate_machine_maker(conn)


@pytest.mark.parametrize('enable,disable', [
    ('INHERIT', 'NOINHERIT'), ('CREATEDB', 'NOCREATEDB'),
    ('CREATEROLE', 'NOCREATEROLE'), ('REPLICATION', 'NOREPLICATION'),
    ('BYPASSRLS', 'NOBYPASSRLS'), ('SUPERUSER', 'NOSUPERUSER'),
])
def test_native_role_profile_drift_is_denied(identity_database, enable, disable):
    dsn, admin = identity_database
    admin.execute(sql.SQL('ALTER ROLE aos_budget_renewal_maker_call {}').format(sql.SQL(enable)))
    try:
        with connect_actor(dsn) as conn:
            with pytest.raises(RenewalIdentityBlocked):
                authenticate_machine_maker(conn)
    finally:
        admin.execute(sql.SQL('ALTER ROLE aos_budget_renewal_maker_call {}').format(sql.SQL(disable)))


def test_native_membership_is_denied_even_without_inheritance(identity_database):
    dsn, admin = identity_database
    admin.execute('CREATE ROLE renewal_fixture_extra NOLOGIN')
    try:
        admin.execute('GRANT renewal_fixture_extra TO aos_budget_renewal_maker_call')
        with connect_actor(dsn) as conn:
            with pytest.raises(RenewalIdentityBlocked):
                authenticate_machine_maker(conn)
    finally:
        admin.execute('REVOKE renewal_fixture_extra FROM aos_budget_renewal_maker_call')
        admin.execute('DROP ROLE renewal_fixture_extra')


def test_native_temporary_schema_is_denied(identity_database):
    dsn, _ = identity_database
    with connect_actor(dsn) as conn:
        conn.execute('CREATE TEMP TABLE renewal_shadow_probe (id integer)')
        with pytest.raises(RenewalIdentityBlocked):
            authenticate_machine_maker(conn)
