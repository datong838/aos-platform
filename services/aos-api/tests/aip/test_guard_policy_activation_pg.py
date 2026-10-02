"""Formal guard source contract in a full-migration disposable PostgreSQL.

Direct inserts below are adversarial attempts and always rolled back. They are
never a source fixture or an accepted activation proof.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from aos_api.db import connect
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate, DataClassificationPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore, materialize_policy, EgressPolicyApprovalRequired, DataPolicyApprovalRequired,
)
from aos_api.extension_runtime.runtime_configuration_candidates import read_candidates
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip._runtime_guard_history_fixture import https_signer, guard_issuer_factory, guard_consumer_factory


def candidate(kind, *, revision=1, lifecycle="draft", identity=None):
    now = datetime.now(timezone.utc)
    common = dict(policyId=identity or "go-"+uuid4().hex, revision=revision,
        effectiveFrom=now-timedelta(minutes=1), effectiveUntil=now+timedelta(hours=1),
        owner="isolated-maker", approvalRef="request-only-not-authority", lifecycle=lifecycle)
    if kind == "egress":
        return EgressPolicyRevisionCreate(**common, allowedSchemes=["https"],
            allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443],
            regionState="confirmed", region="isolated-cn")
    return DataClassificationPolicyRevisionCreate(**common, allowedClassifications=["public_catalog"],
        prohibitedClassifications=["direct_pii","raw_order_detail","customer_conversation", "credential",
                                  "commercial_sensitive","cross_tenant","unknown"])


def publish_draft(kind, item):
    store = AipRuntimeGuardPolicyStore()
    publish = store.publish_egress if kind == "egress" else store.publish_data_classification
    return publish(SCOPE, "isolated-maker", "draft-"+item.policy_id, item)


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_unapproved_active_insert_is_rejected_even_when_store_is_bypassed(kind):
    with isolated_owner(): pass  # Reject any non-disposable database before writes.
    draft = publish_draft(kind, candidate(kind))
    active = candidate(kind, revision=2, lifecycle="active", identity=draft.policy_id)
    materialized = materialize_policy(SCOPE, "isolated-maker", active)
    with connect(SCOPE) as conn:
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match="GUARD_POLICY_CONSUMER_REQUIRED"):
                conn.execute("""INSERT INTO aip_runtime_guard_policy_revision
                    (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                     effective_from,effective_until,payload,created_by,created_at)
                    VALUES(%s,%s,%s,%s,%s,%s,'active',%s,%s,%s,'isolated-adversary',%s)""",
                    (*SCOPE.key,kind,materialized.policy_id,materialized.revision,materialized.content_hash,
                     materialized.effective_from,materialized.effective_until,
                     Jsonb(materialized.model_dump(mode="json",by_alias=True)),materialized.created_at))
        finally:
            conn.rollback()
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_revision WHERE policy_id=%s",
                            (draft.policy_id,)).fetchone()["n"] == 1


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_original_store_still_rejects_text_only_approval(kind):
    with isolated_owner(): pass
    item = candidate(kind, lifecycle="active")
    expected = EgressPolicyApprovalRequired if kind == "egress" else DataPolicyApprovalRequired
    with pytest.raises(expected): publish_draft(kind, item)


@pytest.mark.parametrize("object_id,action_id", [
    ("EgressPolicyRevision","aip_activate_egress_policy"),
    ("DataClassificationPolicyRevision","aip_activate_data_policy"),
])
def test_formal_guard_metadata_is_published_and_reserved(object_id, action_id):
    with isolated_owner() as owner:
        obj = owner.execute("SELECT published FROM meta_object_type WHERE id=%s", (object_id,)).fetchone()
        action = owner.execute("SELECT object_type FROM meta_action_type WHERE id=%s", (action_id,)).fetchone()
        assert obj and obj["published"] is True
        assert action and action["object_type"] == object_id
    with connect(SCOPE) as conn:
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("UPDATE meta_object_type SET name='tampered' WHERE id=%s", (object_id,))
        finally: conn.rollback()


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_activation_target_requires_exact_current_store_draft(kind):
    from aos_api.aip_guard_policy_activation import read_guard_activation_source, GuardActivationBlocked
    with isolated_owner(): pass
    draft = publish_draft(kind, candidate(kind))
    create_type = EgressPolicyRevisionCreate if kind == "egress" else DataClassificationPolicyRevisionCreate
    raw = {k: v for k, v in draft.model_dump(mode="json", by_alias=True).items()
           if k not in {"tenant", "contentHash", "createdBy", "createdAt"}}
    active = create_type.model_validate({**raw, "revision": 2, "lifecycle": "active"})
    with connect(SCOPE) as conn:
        target = read_guard_activation_source(conn, SCOPE, active, expected_version=1)
        assert target.source_content_hash == draft.content_hash
        assert target.revision == 2
        assert target.action_type_id == ("aip_activate_egress_policy" if kind == "egress" else "aip_activate_data_policy")
        with pytest.raises(GuardActivationBlocked, match="HEAD"):
            read_guard_activation_source(conn, SCOPE, active, expected_version=2)
    changed = active.model_copy(update={"owner": "different-owner"})
    with connect(SCOPE) as conn:
        with pytest.raises(GuardActivationBlocked, match="CONTENT"):
            read_guard_activation_source(conn, SCOPE, changed, expected_version=1)
    store = AipRuntimeGuardPolicyStore()
    publish = store.publish_egress if kind == "egress" else store.publish_data_classification
    publish(SCOPE, "isolated-maker", "advance-"+draft.policy_id,
            create_type.model_validate({**raw, "revision": 2}), expected_version=1)
    with connect(SCOPE) as conn:
        with pytest.raises(GuardActivationBlocked, match="HEAD"):
            read_guard_activation_source(conn, SCOPE, active, expected_version=1)


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_source_reader_rejects_scope_mismatch_without_writes(kind):
    from aos_api.aip_guard_policy_activation import read_guard_activation_source, GuardActivationBlocked
    from aos_api.tenant_scope import TenantScope
    with isolated_owner(): pass
    with connect(SCOPE) as conn:
        with pytest.raises(GuardActivationBlocked, match="TENANT_ROLE"):
            read_guard_activation_source(conn, TenantScope("dev-org", "dev-project"),
                                         candidate(kind, revision=2, lifecycle="active"), expected_version=1)


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_internal_maker_writes_only_draft_and_rechecks_membership(kind):
    # Internal Principal fixture only. Signed request and issuer proof is separate.
    from aos_api.auth import Principal
    from aos_api.aip_guard_policy_activation import propose_guard_activation, GuardActivationBlocked
    maker = "go-maker-"+uuid4().hex
    with isolated_owner() as owner:
        owner.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated guard org') ON CONFLICT DO NOTHING",
                      (SCOPE.org_id,))
        owner.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated guard test') ON CONFLICT DO NOTHING",
                      SCOPE.key)
        owner.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",
                      (*SCOPE.key,maker))
    item = candidate(kind)
    publish_draft(kind,item)
    active = type(item).model_validate({**item.model_dump(mode="json",by_alias=True),
                                       "revision":2,"lifecycle":"active"})
    principal = Principal(subject=maker,org_id=SCOPE.org_id,project_id=SCOPE.project_id,token_kind="oidc")
    key = "go-proposal-"+uuid4().hex
    expiry = datetime.now(timezone.utc)+timedelta(minutes=5)
    first = propose_guard_activation(principal,active,expected_version=1,idempotency_key=key,expires_at=expiry)
    assert first.proposal.status.value == "drafted"
    assert first.proposal.risk_level.value == "R2"
    second = propose_guard_activation(principal,active,expected_version=1,idempotency_key=key,expires_at=expiry)
    assert first.proposal.id == second.proposal.id
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_revision WHERE policy_id=%s",
                            (item.policy_id,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s",
                            (first.proposal.id,)).fetchone()["n"] == 0
    with isolated_owner() as owner:
        owner.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                      (*SCOPE.key,maker))
    with pytest.raises(GuardActivationBlocked, match="CURRENT_OWNER"):
        propose_guard_activation(principal,active,expected_version=1,idempotency_key=key,expires_at=expiry)




def signed_guard_case(kind, sign):
    from aos_api.aip_guard_policy_issuer import GuardMakerCommand, propose_guard_signed
    maker,checker = "guard-maker-"+uuid4().hex, "guard-checker-"+uuid4().hex
    with isolated_owner() as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated guard org') ON CONFLICT DO NOTHING", (SCOPE.org_id,))
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated guard workspace') ON CONFLICT DO NOTHING",SCOPE.key)
        for actor in (maker,checker):
            conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,'owner')",(*SCOPE.key,actor))
    item = candidate(kind)
    publish_draft(kind,item)
    active = type(item).model_validate({**item.model_dump(mode="json",by_alias=True),"revision":2,"lifecycle":"active"})
    cmd = GuardMakerCommand(orgId=SCOPE.org_id,projectId=SCOPE.project_id,bearerToken=sign(maker),
        candidate=active,expectedVersion=1,idempotencyKey="guard-signed-maker-"+uuid4().hex,
        expiresAt=datetime.now(timezone.utc)+timedelta(minutes=5))
    return maker,checker,propose_guard_signed(cmd),cmd


def guard_decision(sign, actor, bundle, **changes):
    from aos_api.aip_guard_policy_issuer import GuardDecisionCommand
    raw = dict(orgId=SCOPE.org_id,projectId=SCOPE.project_id,bearerToken=sign(actor),
        proposalId=bundle.proposal.id,idempotencyKey="guard-decision-"+uuid4().hex,
        decision=dict(expectedProposalVersion=bundle.proposal.version,
            expectedProposalHash=bundle.proposal.proposal_hash,decision="approved",reason="isolated formal guard test",
            approvalExpiresAt=datetime.now(timezone.utc)+timedelta(minutes=3)))
    raw.update(changes)
    return GuardDecisionCommand.model_validate(raw)


@pytest.mark.parametrize("kind", ["egress","data_classification"])
def test_signed_independent_checker_records_one_real_approval(kind,https_signer,guard_issuer_factory,tmp_path):
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    sign,requests = https_signer
    maker,checker,bundle,_ = signed_guard_case(kind,sign)
    factory,database = guard_issuer_factory
    attempts = tmp_path/"guard-attempts"; attempts.mkdir(mode=0o700)
    issuer = GuardPolicyIssuer(factory,attempts,expected_database=database)
    command = guard_decision(sign,checker,bundle)
    result = issuer.execute(command)
    assert result["status"] == "observed" and result["decision"] == "approved"
    assert result["activationAuthorized"] is False
    assert issuer.execute(command) == result
    assert issuer.inquire(command) == result
    with connect(SCOPE) as conn:
        events = conn.execute("SELECT actor_id,action_binding_hash FROM aip_action_approval_event WHERE proposal_id=%s",
                              (bundle.proposal.id,)).fetchall()
        assert events == [{"actor_id":checker,"action_binding_hash":bundle.proposal.action_binding_hash}]
        assert conn.execute("SELECT status FROM aip_action_proposal WHERE proposal_id=%s",(bundle.proposal.id,)).fetchone()["status"] == "approved"
    assert len(list(attempts.iterdir())) == 1
    assert len(requests) >= 4


@pytest.mark.parametrize("bad",["self","revoked","wrong_signature","cross_tenant"])
def test_signed_checker_invalid_authority_never_attempts(bad,https_signer,guard_issuer_factory,tmp_path):
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer, GuardIssuerBlocked
    sign,_ = https_signer
    maker,checker,bundle,_ = signed_guard_case("egress",sign)
    command = guard_decision(sign,maker if bad=="self" else checker,bundle)
    if bad=="revoked":
        with isolated_owner() as conn:
            conn.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,checker))
    from pydantic import SecretStr
    if bad=="wrong_signature": command.bearer_token = SecretStr(sign(checker,wrong_key=True))
    if bad=="cross_tenant": command.bearer_token = SecretStr(sign(checker,changes={"org_id":"dev-org"}))
    attempts=tmp_path/"attempts";attempts.mkdir(mode=0o700)
    factory,database=guard_issuer_factory
    with pytest.raises(GuardIssuerBlocked):
        GuardPolicyIssuer(factory,attempts,expected_database=database).execute(command)
    assert list(attempts.iterdir()) == []
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s",
                            (bundle.proposal.id,)).fetchone()["n"] == 0


@pytest.mark.parametrize("when",["before_commit","after_commit"])
def test_unknown_decision_never_reexecutes(when,https_signer,guard_issuer_factory,tmp_path):
    from contextlib import contextmanager
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    sign,_=https_signer
    _,checker,bundle,_=signed_guard_case("egress",sign)
    base,database=guard_issuer_factory
    write_calls=[]
    @contextmanager
    def faulty(scope,read_only):
        if not read_only: write_calls.append(True)
        decision_call = not read_only and len(write_calls)==2
        with base(scope,read_only) as conn:
            yield conn
            if decision_call and when=="before_commit":
                raise ConnectionError("injected transport loss before commit")
        if decision_call and when=="after_commit":
            raise ConnectionError("injected transport loss after commit")
    attempts=tmp_path/"attempts";attempts.mkdir(mode=0o700)
    issuer=GuardPolicyIssuer(faulty,attempts,expected_database=database)
    command=guard_decision(sign,checker,bundle)
    first=issuer.execute(command)
    assert first["status"] == ("observed" if when=="after_commit" else "unresolved")
    assert issuer.execute(command)==first
    assert issuer.inquire(command)==first
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s",
                            (bundle.proposal.id,)).fetchone()["n"] == (1 if when=="after_commit" else 0)
    assert len(list(attempts.iterdir()))==1


def test_runtime_cannot_impersonate_private_issuer(https_signer,tmp_path):
    from contextlib import contextmanager
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer,GuardIssuerBlocked
    sign,_=https_signer
    _,checker,bundle,_=signed_guard_case("egress",sign)
    @contextmanager
    def wrong_factory(scope,read_only):
        with connect(scope) as conn: yield conn
    with isolated_owner() as owner: database=owner.info.dbname
    attempts=tmp_path/"attempts";attempts.mkdir(mode=0o700)
    with pytest.raises(GuardIssuerBlocked,match="DATABASE_IDENTITY"):
        GuardPolicyIssuer(wrong_factory,attempts,expected_database=database).execute(guard_decision(sign,checker,bundle))
    assert list(attempts.iterdir())==[]


def test_guard_approval_expiring_during_insert_rolls_back(https_signer,guard_issuer_factory,tmp_path):
    from psycopg import sql
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    sign,_=https_signer
    _,checker,bundle,_=signed_guard_case("egress",sign)
    factory,database=guard_issuer_factory
    attempts=tmp_path/"attempts";attempts.mkdir(mode=0o700)
    # Fault injection only: delay the real INSERT, without changing its authority checks.
    with isolated_owner() as conn:
        conn.execute("CREATE SEQUENCE guard_test_delay_seen")
        conn.execute("GRANT USAGE ON SEQUENCE guard_test_delay_seen TO aos_runtime")
        conn.execute(sql.SQL("""CREATE FUNCTION guard_test_delay() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN IF NEW.proposal_id={} THEN PERFORM nextval('guard_test_delay_seen');
          PERFORM pg_sleep(1.8); END IF; RETURN NEW; END $$""").format(sql.Literal(bundle.proposal.id)))
        conn.execute("CREATE TRIGGER zz_guard_test_delay BEFORE INSERT ON aip_action_approval_event FOR EACH ROW EXECUTE FUNCTION guard_test_delay()")
    try:
        command=guard_decision(sign,checker,bundle)
        command.decision.approval_expires_at=datetime.now(timezone.utc)+timedelta(seconds=1.5)
        result=GuardPolicyIssuer(factory,attempts,expected_database=database).execute(command)
        assert result["status"]=="unresolved"
        with isolated_owner() as conn:
            # Sequences are not rolled back: proves the delayed INSERT was reached.
            assert conn.execute("SELECT is_called FROM guard_test_delay_seen").fetchone()["is_called"] is True
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s",
                                (bundle.proposal.id,)).fetchone()["n"]==0
            assert conn.execute("SELECT status FROM aip_action_proposal WHERE proposal_id=%s",
                                (bundle.proposal.id,)).fetchone()["status"]=="drafted"
    finally:
        with isolated_owner() as conn:
            conn.execute("DROP TRIGGER zz_guard_test_delay ON aip_action_approval_event")
            conn.execute("DROP FUNCTION guard_test_delay()")
            conn.execute("DROP SEQUENCE guard_test_delay_seen")




def approved_guard_case(kind,sign,guard_issuer_factory,tmp_path):
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    maker,checker,bundle,maker_command=signed_guard_case(kind,sign)
    factory,database=guard_issuer_factory
    folder=tmp_path/("issuer-"+uuid4().hex);folder.mkdir(mode=0o700)
    approval=GuardPolicyIssuer(factory,folder,expected_database=database).execute(guard_decision(sign,checker,bundle))
    assert approval["status"]=="observed"
    return maker,checker,bundle,maker_command,approval


def guard_consume_command(sign,maker,bundle,approval):
    from aos_api.aip_guard_policy_consumer import GuardConsumeCommand
    return GuardConsumeCommand(orgId=SCOPE.org_id,projectId=SCOPE.project_id,bearerToken=sign(maker),
        proposalId=bundle.proposal.id,approvalEventId=approval["approvalEventId"],
        proposalHash=bundle.proposal.proposal_hash,targetContentHash=bundle.proposal.payload["targetContentHash"],
        bindingHash=bundle.proposal.action_binding_hash)


def test_signed_guard_pair_consumes_and_provider_reads_exact_sources(https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    from types import SimpleNamespace
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef
    from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer
    sign,_=https_signer
    factory,database=guard_consumer_factory
    folder=tmp_path/"consumer-attempts";folder.mkdir(mode=0o700)
    consumer=GuardPolicyConsumer(factory,folder,expected_database=database)
    with connect(SCOPE) as conn:
        before=read_candidates(conn,SCOPE).counts
    refs={}
    for kind in ("egress","data_classification"):
        maker,_,bundle,_,approval=approved_guard_case(kind,sign,guard_issuer_factory,tmp_path)
        command=guard_consume_command(sign,maker,bundle,approval)
        result=consumer.execute(command)
        assert result["status"]=="observed"
        assert consumer.execute(command)==result
        assert consumer.inquire(command)==result
        ref=result["result"]
        refs[kind]=VersionedAssetRef(assetType=ref["resourceType"],assetId=ref["resourceId"],
                                    revision=ref["revision"],contentHash=ref["contentHash"])
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_receipt WHERE operation=%s AND idempotency_key=%s",
                                ("guard_policy."+kind+".activate",bundle.proposal.id)).fetchone()["n"]==1
    # Real guard Store validates exact active revisions. No Provider is started or called.
    AipRuntimeGuardPolicyStore().require_provider_dependencies(SCOPE,SimpleNamespace(
        egress_policy_ref=refs["egress"],data_classification_policy_ref=refs["data_classification"],
        endpoint_profile=SimpleNamespace(base_url="https://api.agnes-ai.cn",region="isolated-cn")))
    with connect(SCOPE) as conn:
        after=read_candidates(conn,SCOPE).counts
    assert after["egress_policies"]==before["egress_policies"]+1
    assert after["data_policies"]==before["data_policies"]+1
    for field in set(before)-{"egress_policies","data_policies"}:
        assert after[field]==before[field]
    assert len(list(folder.iterdir()))==2


@pytest.mark.parametrize("bad",["target_hash","binding_hash","wrong_actor","checker_revoked","head_advanced","withdrawn","wrong_signature","cross_tenant"])
def test_consumer_rejects_invalid_authority_without_receipt(bad,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    from pydantic import SecretStr
    from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer
    from aos_api.aip_guard_policy_issuer import GuardIssuerBlocked
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_action_models import WithdrawActionProposalRequest
    sign,_=https_signer
    maker,checker,bundle,maker_command,approval=approved_guard_case("egress",sign,guard_issuer_factory,tmp_path)
    command=guard_consume_command(sign,maker,bundle,approval)
    if bad=="target_hash":command.target_content_hash="a"*64
    if bad=="binding_hash":command.binding_hash="b"*64
    if bad=="wrong_actor":command.bearer_token=SecretStr(sign(checker))
    if bad=="wrong_signature":command.bearer_token=SecretStr(sign(maker,wrong_key=True))
    if bad=="cross_tenant":command.bearer_token=SecretStr(sign(maker,changes={"org_id":"dev-org"}))
    if bad=="checker_revoked":
        with isolated_owner() as conn:
            conn.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",(*SCOPE.key,checker))
    if bad=="head_advanced":
        draft=EgressPolicyRevisionCreate.model_validate({**maker_command.candidate.model_dump(mode="json",by_alias=True),"lifecycle":"draft"})
        AipRuntimeGuardPolicyStore().publish_egress(SCOPE,maker,"advance-"+uuid4().hex,draft,expected_version=1)
    if bad=="withdrawn":
        AipActionStore().withdraw(SCOPE,maker,bundle.proposal.id,"withdraw-"+uuid4().hex,
            WithdrawActionProposalRequest(expectedProposalVersion=2,expectedProposalHash=bundle.proposal.proposal_hash,reason="isolated withdrawal"))
    factory,database=guard_consumer_factory
    folder=tmp_path/"consume-attempts";folder.mkdir(mode=0o700)
    with pytest.raises((psycopg.errors.InsufficientPrivilege,GuardIssuerBlocked)):
        GuardPolicyConsumer(factory,folder,expected_database=database).execute(command)
    assert list(folder.iterdir())==[]
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_receipt WHERE idempotency_key=%s",
                            (bundle.proposal.id,)).fetchone()["n"]==0


@pytest.mark.parametrize("when",["before_commit","after_commit"])
def test_consumer_unknown_never_reexecutes(when,https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    from contextlib import contextmanager
    from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer
    sign,_=https_signer
    maker,_,bundle,_,approval=approved_guard_case("data_classification",sign,guard_issuer_factory,tmp_path)
    command=guard_consume_command(sign,maker,bundle,approval)
    base,database=guard_consumer_factory
    writes=[]
    @contextmanager
    def faulty(scope,read_only):
        if not read_only:writes.append(True)
        with base(scope,read_only) as conn:
            yield conn
            if not read_only and when=="before_commit":raise ConnectionError("injected before commit")
        if not read_only and when=="after_commit":raise ConnectionError("injected after commit")
    folder=tmp_path/"consume-attempts";folder.mkdir(mode=0o700)
    consumer=GuardPolicyConsumer(faulty,folder,expected_database=database)
    first=consumer.execute(command)
    assert first["status"]==("observed" if when=="after_commit" else "unresolved")
    assert consumer.execute(command)==first
    assert len(writes)==1
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_receipt WHERE idempotency_key=%s",
                            (bundle.proposal.id,)).fetchone()["n"]==(1 if when=="after_commit" else 0)


def test_guard_consumer_caller_has_no_table_access_or_role_switch(guard_consumer_factory):
    from psycopg import sql
    factory,_=guard_consumer_factory
    for table in ("aip_action_proposal","aip_action_approval_event","aip_runtime_guard_policy_revision","aip_runtime_guard_policy_receipt"):
        with factory(SCOPE,False) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SELECT * FROM {} LIMIT 1").format(sql.Identifier(table)))
            conn.rollback()
    for role in ("aos_runtime","aos_guard_approval_issuer","aos_guard_policy_consumer_owner"):
        with factory(SCOPE,False) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
            conn.rollback()


def test_concurrent_consume_has_one_receipt(https_signer,guard_issuer_factory,guard_consumer_factory,tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer
    from aos_api.aip_network_issuer_attempt import AttemptUnknown
    sign,_=https_signer
    maker,_,bundle,_,approval=approved_guard_case("egress",sign,guard_issuer_factory,tmp_path)
    command=guard_consume_command(sign,maker,bundle,approval)
    factory,database=guard_consumer_factory
    folder=tmp_path/"consume-attempts";folder.mkdir(mode=0o700)
    consumer=GuardPolicyConsumer(factory,folder,expected_database=database)
    def consume():
        try:return consumer.execute(command)
        except AttemptUnknown:return {"status":"unresolved"}  # Incomplete concurrent marker is never permission to resend.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:consume(),range(2)))
    assert all(r["status"] in {"observed","unresolved"} for r in results)
    assert consumer.inquire(command)["status"]=="observed"
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_receipt WHERE idempotency_key=%s",
                            (bundle.proposal.id,)).fetchone()["n"]==1


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_guard_consumer_expiring_during_receipt_rolls_back(
    kind, https_signer, guard_issuer_factory, guard_consumer_factory, tmp_path,
):
    from psycopg import sql
    from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
    from aos_api.aip_guard_policy_consumer import GuardPolicyConsumer

    sign, _ = https_signer
    maker, checker, bundle, maker_command = signed_guard_case(kind, sign)
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
        conn.execute("CREATE TRIGGER zz_guard_consume_delay BEFORE INSERT ON aip_runtime_guard_policy_receipt FOR EACH ROW EXECUTE FUNCTION guard_consume_delay()")
    try:
        decision = guard_decision(sign, checker, bundle)
        decision.decision.approval_expires_at = datetime.now(timezone.utc) + timedelta(seconds=1.5)
        approval = GuardPolicyIssuer(issuer_factory, issuer_folder, expected_database=database).execute(decision)
        assert approval["status"] == "observed"
        command = guard_consume_command(sign, maker, bundle, approval)
        result = GuardPolicyConsumer(consumer_factory, consumer_folder, expected_database=consumer_database).execute(command)
        assert result["status"] == "unresolved"
        with isolated_owner() as conn:
            assert conn.execute("SELECT is_called FROM guard_consume_delay_seen").fetchone()["is_called"] is True
        with connect(SCOPE) as conn:
            policy_id = maker_command.candidate.policy_id
            assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_revision WHERE policy_id=%s AND lifecycle='active'", (policy_id,)).fetchone()["n"] == 0
            head = conn.execute("SELECT current_revision,version FROM aip_runtime_guard_policy_head WHERE policy_id=%s", (policy_id,)).fetchone()
            assert (head["current_revision"], head["version"]) == (1, 1)
            assert conn.execute("SELECT count(*) AS n FROM aip_runtime_guard_policy_receipt WHERE idempotency_key=%s", (bundle.proposal.id,)).fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM aip_action_approval_event WHERE proposal_id=%s", (bundle.proposal.id,)).fetchone()["n"] == 1
    finally:
        with isolated_owner() as conn:
            conn.execute("DROP TRIGGER zz_guard_consume_delay ON aip_runtime_guard_policy_receipt")
            conn.execute("DROP FUNCTION guard_consume_delay()")
            conn.execute("DROP SEQUENCE guard_consume_delay_seen")
