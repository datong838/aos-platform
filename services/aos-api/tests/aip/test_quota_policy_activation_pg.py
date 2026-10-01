"""Formal quota source gates in the full-migration disposable PostgreSQL."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore, materialize_policy, QuotaPolicyApprovalRequired,
)
from aos_api.db import connect
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


def quota_candidate(*, identity=None, revision=1, lifecycle="draft"):
    now = datetime.now(timezone.utc)
    return QuotaPolicyRevisionCreate(
        policyId=identity or "gp-" + uuid4().hex, revision=revision, lifecycle=lifecycle,
        effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(hours=1),
        owner="isolated-quota-maker", approvalRef="request-not-approval",
        maxConcurrency=2, maxInputTokens=8000, maxOutputTokens=2000,
        hourlyRequestLimit=50, dailyRequestLimit=200, reservationLeaseSeconds=60,
        overflowBehavior="queue", allowPublicProviderFallback=False, allowAutoScale=False,
    )


def test_quota_store_still_rejects_text_only_approval():
    with isolated_owner(): pass
    with pytest.raises(QuotaPolicyApprovalRequired):
        AipModelGovernancePolicyStore().publish_quota(
            SCOPE, "isolated-quota-maker", "gp-"+uuid4().hex, quota_candidate(lifecycle="active"))


def test_runtime_cannot_insert_unapproved_active_quota():
    with isolated_owner(): pass
    draft = AipModelGovernancePolicyStore().publish_quota(
        SCOPE, "isolated-quota-maker", "gp-"+uuid4().hex, quota_candidate())
    active = materialize_policy(SCOPE, "isolated-quota-maker", quota_candidate(
        identity=draft.policy_id, revision=2, lifecycle="active"))
    with connect(SCOPE) as conn:
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match="QUOTA_POLICY_CONSUMER_REQUIRED"):
                conn.execute("""INSERT INTO aip_model_governance_policy_revision
                    (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                     effective_from,effective_until,payload,created_by,created_at)
                    VALUES(%s,%s,'quota',%s,%s,%s,'active',%s,%s,%s,%s,%s)""",
                    (*SCOPE.key, active.policy_id, active.revision, active.content_hash,
                     active.effective_from, active.effective_until,
                     Jsonb(active.model_dump(mode="json", by_alias=True)), active.created_by, active.created_at))
        finally:
            conn.rollback()


def test_formal_quota_metadata_exists():
    with isolated_owner() as conn:
        assert conn.execute("SELECT id FROM meta_object_type WHERE id='QuotaPolicyRevision'").fetchone()
        assert conn.execute("SELECT id FROM meta_action_type WHERE id='aip_activate_quota_policy'").fetchone()


def signed_quota_case(sign):
    from aos_api.aip_guard_policy_issuer import GuardMakerCommand, propose_guard_signed
    maker, checker = "quota-maker-"+uuid4().hex, "quota-checker-"+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated quota') ON CONFLICT DO NOTHING", (SCOPE.org_id,))
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated quota') ON CONFLICT DO NOTHING", SCOPE.key)
        for actor in (maker, checker):
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')", (*SCOPE.key,actor))
    item = quota_candidate()
    AipModelGovernancePolicyStore().publish_quota(SCOPE, maker, "draft-"+uuid4().hex, item)
    active = QuotaPolicyRevisionCreate.model_validate({**item.model_dump(mode="json", by_alias=True), "revision":2,"lifecycle":"active"})
    command = GuardMakerCommand(orgId=SCOPE.org_id,projectId=SCOPE.project_id,bearerToken=sign(maker),
        candidate=active,expectedVersion=1,idempotencyKey="quota-propose-"+uuid4().hex,
        expiresAt=datetime.now(timezone.utc)+timedelta(minutes=5))
    return maker, checker, propose_guard_signed(command), command


def test_signed_quota_maker_and_independent_checker(https_signer, guard_issuer_factory, tmp_path):
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    from tests.aip.test_guard_policy_activation_pg import guard_decision
    sign, requests = https_signer
    maker, checker, bundle, _ = signed_quota_case(sign)
    factory, database = guard_issuer_factory
    folder = tmp_path / "quota-issuer-attempts"
    folder.mkdir(mode=0o700)
    issuer = GuardPolicyIssuer(factory, folder, expected_database=database)
    decision = guard_decision(sign, checker, bundle)
    result = issuer.execute(decision)
    assert result["status"] == "observed" and result["activationAuthorized"] is False
    assert issuer.execute(decision) == result
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s", (bundle.proposal.id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_revision WHERE policy_id=%s AND lifecycle='active'", (bundle.proposal.payload["candidate"]["policyId"],)).fetchone()["n"] == 0
    assert requests


def approved_quota(sign, guard_issuer_factory, tmp_path):
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    from tests.aip.test_guard_policy_activation_pg import guard_decision
    maker, checker, bundle, command = signed_quota_case(sign)
    factory, database = guard_issuer_factory
    folder = tmp_path / ("quota-issuer-"+uuid4().hex)
    folder.mkdir(mode=0o700)
    approval = GuardPolicyIssuer(factory,folder,expected_database=database).execute(guard_decision(sign,checker,bundle))
    assert approval["status"] == "observed"
    return maker, checker, bundle, command, approval


def test_signed_quota_consumes_once_and_original_reader_accepts(
    https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path,
):
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from tests.aip.test_guard_policy_activation_pg import guard_consume_command
    sign, _ = https_signer
    maker, _, bundle, _, approval = approved_quota(sign,guard_issuer_factory,tmp_path)
    command = guard_consume_command(sign,maker,bundle,approval)
    factory,database = guard_consumer_factory
    folder = tmp_path / "quota-consumer-attempts"
    folder.mkdir(mode=0o700)
    consumer = QuotaPolicyConsumer(factory,folder,expected_database=database)
    result = consumer.execute(command)
    assert result["status"] == "observed"
    assert consumer.execute(command) == result
    assert consumer.inquire(command) == result
    ref = result["result"]
    saved = AipModelGovernancePolicyStore().require_exact_active(SCOPE,VersionedAssetRef(
        assetType=ref["resourceType"],assetId=ref["resourceId"],revision=ref["revision"],contentHash=ref["contentHash"]))
    assert saved.revision == 2 and saved.max_concurrency == 2
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE operation='model_governance_policy.quota.activate' AND idempotency_key=%s",(bundle.proposal.id,)).fetchone()["n"] == 1


@pytest.mark.parametrize("bad", ["target", "binding", "wrong_actor", "wrong_signature", "tenant", "checker_revoked", "head_advanced", "withdrawn"])
def test_quota_consumer_rejects_drift_before_attempt(bad, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path):
    from pydantic import SecretStr
    from aos_api.aip_guard_policy_issuer import GuardIssuerBlocked
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_action_models import WithdrawActionProposalRequest
    from tests.aip.test_guard_policy_activation_pg import guard_consume_command
    sign, _ = https_signer
    maker, checker, bundle, maker_command, approval = approved_quota(sign,guard_issuer_factory,tmp_path)
    command = guard_consume_command(sign,maker,bundle,approval)
    if bad == "target": command.target_content_hash = "a"*64
    if bad == "binding": command.binding_hash = "b"*64
    if bad == "wrong_actor": command.bearer_token = SecretStr(sign(checker))
    if bad == "wrong_signature": command.bearer_token = SecretStr(sign(maker,wrong_key=True))
    if bad == "tenant": command.bearer_token = SecretStr(sign(maker,changes={"org_id":"dev-org"}))
    if bad == "checker_revoked":
        with isolated_owner() as conn:
            conn.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,checker))
    if bad == "head_advanced":
        draft = QuotaPolicyRevisionCreate.model_validate({**maker_command.candidate.model_dump(mode="json",by_alias=True),"lifecycle":"draft"})
        AipModelGovernancePolicyStore().publish_quota(SCOPE,maker,"advance-"+uuid4().hex,draft,expected_version=1)
    if bad == "withdrawn":
        AipActionStore().withdraw(SCOPE,maker,bundle.proposal.id,"withdraw-"+uuid4().hex,
            WithdrawActionProposalRequest(expectedProposalVersion=2,expectedProposalHash=bundle.proposal.proposal_hash,reason="isolated withdrawal"))
    factory,database = guard_consumer_factory
    folder = tmp_path / "quota-consumer-attempts"
    folder.mkdir(mode=0o700)
    with pytest.raises((psycopg.errors.InsufficientPrivilege,GuardIssuerBlocked)):
        QuotaPolicyConsumer(factory,folder,expected_database=database).execute(command)
    assert list(folder.iterdir()) == []
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE idempotency_key=%s",(bundle.proposal.id,)).fetchone()["n"] == 0


@pytest.mark.parametrize("committed", [False, True])
def test_quota_unknown_result_is_never_written_again(committed, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path):
    from contextlib import contextmanager
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from tests.aip.test_guard_policy_activation_pg import guard_consume_command
    sign, _ = https_signer
    maker, _, bundle, _, approval = approved_quota(sign,guard_issuer_factory,tmp_path)
    command = guard_consume_command(sign,maker,bundle,approval)
    base,database = guard_consumer_factory
    writes = []
    @contextmanager
    def fault(scope, read_only):
        if not read_only: writes.append(True)
        with base(scope,read_only) as conn:
            yield conn
            if not read_only and not committed: raise ConnectionError("before commit")
        if not read_only and committed: raise ConnectionError("after commit")
    folder = tmp_path / "quota-consumer-attempts"
    folder.mkdir(mode=0o700)
    consumer = QuotaPolicyConsumer(fault,folder,expected_database=database)
    first = consumer.execute(command)
    assert first["status"] == ("observed" if committed else "unresolved")
    assert consumer.execute(command) == first
    assert len(writes) == 1
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE idempotency_key=%s",(bundle.proposal.id,)).fetchone()["n"] == int(committed)


def test_quota_consumer_expiring_during_receipt_rolls_back(
    https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path,
):
    from psycopg import sql
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from tests.aip.test_guard_policy_activation_pg import guard_decision, guard_consume_command

    sign, _ = https_signer
    maker, checker, bundle, maker_command = signed_quota_case(sign)
    issuer_factory, database = guard_issuer_factory
    consumer_factory, consumer_database = guard_consumer_factory
    issuer_folder = tmp_path / "issuer"
    consumer_folder = tmp_path / "expiry-consumer-attempts"
    issuer_folder.mkdir(mode=0o700)
    consumer_folder.mkdir(mode=0o700)
    with isolated_owner() as conn:
        conn.execute("CREATE SEQUENCE guard_consume_delay_seen")
        conn.execute("GRANT USAGE ON SEQUENCE guard_consume_delay_seen TO aos_guard_policy_consumer_owner")
        conn.execute(sql.SQL("""CREATE FUNCTION guard_consume_delay() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF NEW.idempotency_key={} THEN
            PERFORM nextval('public.guard_consume_delay_seen');
            PERFORM pg_sleep(1.8);
          END IF; RETURN NEW; END $$""").format(sql.Literal(bundle.proposal.id)))
        conn.execute("CREATE TRIGGER zz_guard_consume_delay BEFORE INSERT ON aip_model_governance_policy_receipt FOR EACH ROW EXECUTE FUNCTION guard_consume_delay()")
    try:
        decision = guard_decision(sign, checker, bundle)
        decision.decision.approval_expires_at = datetime.now(timezone.utc) + timedelta(seconds=1.5)
        approval = GuardPolicyIssuer(issuer_factory, issuer_folder, expected_database=database).execute(decision)
        assert approval["status"] == "observed"
        command = guard_consume_command(sign, maker, bundle, approval)
        result = QuotaPolicyConsumer(consumer_factory, consumer_folder, expected_database=consumer_database).execute(command)
        assert result["status"] == "unresolved"
        with isolated_owner() as conn:
            assert conn.execute("SELECT is_called FROM guard_consume_delay_seen").fetchone()["is_called"] is True
        with connect(SCOPE) as conn:
            policy_id = maker_command.candidate.policy_id
            assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_revision WHERE policy_id=%s AND lifecycle='active'", (policy_id,)).fetchone()["n"] == 0
            head = conn.execute("SELECT current_revision,version FROM aip_model_governance_policy_head WHERE policy_id=%s", (policy_id,)).fetchone()
            assert (head["current_revision"], head["version"]) == (1, 1)
            assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE idempotency_key=%s", (bundle.proposal.id,)).fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s", (bundle.proposal.id,)).fetchone()["n"] == 1
    finally:
        with isolated_owner() as conn:
            conn.execute("DROP TRIGGER zz_guard_consume_delay ON aip_model_governance_policy_receipt")
            conn.execute("DROP FUNCTION guard_consume_delay()")
            conn.execute("DROP SEQUENCE guard_consume_delay_seen")


def test_quota_concurrent_consume_has_one_receipt(https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_quota_policy_consumer import QuotaPolicyConsumer
    from aos_api.aip_network_issuer_attempt import AttemptUnknown
    from tests.aip.test_guard_policy_activation_pg import guard_consume_command
    sign, _ = https_signer
    maker, _, bundle, _, approval = approved_quota(sign,guard_issuer_factory,tmp_path)
    command = guard_consume_command(sign,maker,bundle,approval)
    factory,database = guard_consumer_factory
    folder = tmp_path / "quota-concurrent-attempts"
    folder.mkdir(mode=0o700)
    consumer = QuotaPolicyConsumer(factory,folder,expected_database=database)
    def attempt(_):
        try: return consumer.execute(command)
        except AttemptUnknown: return {"status":"unresolved"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt,range(2)))
    assert all(result["status"] in {"observed","unresolved"} for result in results)
    assert consumer.inquire(command)["status"] == "observed"
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_model_governance_policy_receipt WHERE idempotency_key=%s",(bundle.proposal.id,)).fetchone()["n"] == 1


def test_quota_caller_cannot_read_governance_tables(guard_consumer_factory):
    from psycopg import sql
    factory, _ = guard_consumer_factory
    for table in ("aip_model_governance_policy_head", "aip_model_governance_policy_revision", "aip_model_governance_policy_receipt"):
        with factory(SCOPE,False) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.Identifier(table)))
            conn.rollback()


@pytest.mark.parametrize("change", [
    {"max_concurrency":3}, {"max_input_tokens":8001}, {"max_output_tokens":2001},
    {"daily_request_limit":49}, {"rpm_limit":1}, {"allow_auto_scale":True},
])
def test_quota_target_revalidates_mutated_limits(change):
    from aos_api.aip_guard_policy_activation import build_guard_activation_target, GuardActivationBlocked
    item = quota_candidate()
    draft = materialize_policy(SCOPE,"maker",item)
    active = QuotaPolicyRevisionCreate.model_validate({**item.model_dump(mode="json",by_alias=True),"revision":2,"lifecycle":"active"})
    with pytest.raises(GuardActivationBlocked):
        build_guard_activation_target(scope=SCOPE,draft=draft,candidate=active.model_copy(update=change),expected_version=1)


@pytest.mark.parametrize("replacement", ["suspended", "draft"])
def test_old_quota_cannot_authorize_after_head_changes(replacement):
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_model_governance_policy_store import ModelGovernancePolicyDependencyBlocked
    from tests.aip._model_governance_history_fixture import seed_historical_model_policy
    store = AipModelGovernancePolicyStore()
    active = seed_historical_model_policy(SCOPE,"quota-reader-maker",quota_candidate(lifecycle="active"))
    ref = VersionedAssetRef(assetType="QuotaPolicyRevision",assetId=active.policy_id,
        revision=active.revision,contentHash=active.content_hash)
    assert store.require_exact_active(SCOPE,ref) == active
    body = active.model_dump(mode="json",by_alias=True)
    candidate = QuotaPolicyRevisionCreate.model_validate({
        **{k:v for k,v in body.items() if k not in {"tenant","contentHash","createdBy","createdAt"}},
        "revision":3,"lifecycle":replacement,
    })
    store.publish_quota(SCOPE,"quota-reader-maker","withdraw-"+uuid4().hex,candidate,expected_version=2)
    assert store.get_quota(SCOPE,active.policy_id,2) == active
    with pytest.raises(ModelGovernancePolicyDependencyBlocked,match="current active"):
        store.require_exact_active(SCOPE,ref)


def test_quota_current_head_lock_lasts_until_outer_transaction_ends():
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.db import connect_serializable
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from tests.aip._model_governance_history_fixture import seed_historical_model_policy
    active = seed_historical_model_policy(SCOPE,"quota-lock-maker",quota_candidate(lifecycle="active"))
    ref = VersionedAssetRef(assetType="QuotaPolicyRevision",assetId=active.policy_id,revision=2,contentHash=active.content_hash)
    with connect_serializable(SCOPE) as conn:
        bound = TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
        assert AipModelGovernancePolicyStore(bound).require_exact_active(SCOPE,ref) == active
        with pytest.raises(psycopg.errors.LockNotAvailable):
            with connect(SCOPE) as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                other.execute("UPDATE aip_model_governance_policy_head SET version=version WHERE org_id=%s AND project_id=%s AND policy_kind='quota' AND policy_id=%s",(*SCOPE.key,active.policy_id))


def test_quota_stale_serializable_snapshot_cannot_admit_old_head():
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.db import connect_serializable
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from tests.aip._model_governance_history_fixture import seed_historical_model_policy
    store = AipModelGovernancePolicyStore()
    active = seed_historical_model_policy(SCOPE,"quota-stale-maker",quota_candidate(lifecycle="active"))
    ref = VersionedAssetRef(assetType="QuotaPolicyRevision",assetId=active.policy_id,revision=2,contentHash=active.content_hash)
    with connect_serializable(SCOPE) as conn:
        conn.execute("SELECT current_revision FROM aip_model_governance_policy_head WHERE org_id=%s AND project_id=%s AND policy_kind='quota' AND policy_id=%s",(*SCOPE.key,active.policy_id)).fetchone()
        raw = active.model_dump(mode="json",by_alias=True)
        suspended = QuotaPolicyRevisionCreate.model_validate({**{k:v for k,v in raw.items() if k not in {"tenant","contentHash","createdBy","createdAt"}},"revision":3,"lifecycle":"suspended"})
        store.publish_quota(SCOPE,"quota-stale-maker","withdraw-"+uuid4().hex,suspended,expected_version=2)
        bound = TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
        with pytest.raises(psycopg.errors.SerializationFailure):
            AipModelGovernancePolicyStore(bound).require_exact_active(SCOPE,ref)
        conn.rollback()
