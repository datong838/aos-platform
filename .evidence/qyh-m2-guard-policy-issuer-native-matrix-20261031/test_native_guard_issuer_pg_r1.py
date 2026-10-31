"""Retained native PG matrix for the isolated guard issuer r1 resource only."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from pydantic import SecretStr

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_guard_policy_issuer import (
    GuardDecisionCommand,
    GuardIssuerBlocked,
    GuardMakerCommand,
    GuardPolicyIssuer,
    propose_guard_signed,
)
from aos_api.aip_guard_policy_issuer_connection import (
    GuardIssuerDatabaseConfig,
    connect_guard_issuer,
)
from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevisionCreate,
)
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.auth import Principal
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from tests.aip._runtime_guard_history_fixture import https_signer


SCOPE = TenantScope("org-org", "dev-project")
EXPECTED_DATABASE = "aos_guard_issuer_native_r1"
EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 18459
PRIVATE_ROOT = Path(
    "/Users/ddt/work/projects/ai_agent/aos-recovery/"
    "qyh-m2-guard-issuer-native-r1-20261031"
)


@contextmanager
def exact_owner():
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        assert conn.info.host == EXPECTED_HOST
        assert conn.info.port == EXPECTED_PORT
        assert conn.info.dbname == EXPECTED_DATABASE
        identity = conn.execute(
            "SELECT session_user AS session_user,current_user AS current_user"
        ).fetchone()
        assert identity == {"session_user": "aos_app", "current_user": "aos_app"}
        yield conn


@pytest.fixture(scope="module")
def issuer_connection():
    state = PRIVATE_ROOT / "pg-matrix-r2"
    state.mkdir(mode=0o700, exist_ok=False)
    passfile = state / "guard-issuer-pgpass"
    password = secrets.token_urlsafe(32)
    passfile.write_text(
        f"{EXPECTED_HOST}:{EXPECTED_PORT}:{EXPECTED_DATABASE}:"
        f"aos_guard_approval_issuer:{password}\n"
    )
    passfile.chmod(0o600)
    config = GuardIssuerDatabaseConfig(
        host=EXPECTED_HOST,
        port=EXPECTED_PORT,
        database=EXPECTED_DATABASE,
        passfile=passfile,
    )
    with exact_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('guard-issuer-native-r1'))")
        original = admin.execute(
            "SELECT rolcanlogin,rolpassword IS NULL AS no_password "
            "FROM pg_authid WHERE rolname='aos_guard_approval_issuer'"
        ).fetchone()
        assert original == {"rolcanlogin": False, "no_password": True}
        admin.execute(
            sql.SQL("ALTER ROLE aos_guard_approval_issuer LOGIN PASSWORD {}")
            .format(sql.Literal(password))
        )
        admin.commit()
        try:
            yield (
                lambda scope, read_only: connect_guard_issuer(
                    config, scope, read_only
                ),
                state,
            )
        finally:
            admin.execute(
                "ALTER ROLE aos_guard_approval_issuer NOLOGIN PASSWORD NULL"
            )
            admin.commit()
            passfile.write_text("# removed temporary guard issuer credential\n")
            passfile.chmod(0o600)
            assert admin.execute(
                "SELECT rolcanlogin,rolpassword IS NULL AS no_password "
                "FROM pg_authid WHERE rolname='aos_guard_approval_issuer'"
            ).fetchone() == original
            admin.execute(
                "SELECT pg_advisory_unlock(hashtext('guard-issuer-native-r1'))"
            )


def candidate(kind: str):
    now = datetime.now(timezone.utc)
    common = dict(
        policyId=f"synthetic-native-r1-{kind}-{uuid4().hex}",
        revision=1,
        effectiveFrom=now - timedelta(minutes=1),
        effectiveUntil=now + timedelta(hours=1),
        owner="synthetic-native-r1-maker",
        approvalRef="synthetic-native-r1-not-authority",
        lifecycle="draft",
    )
    if kind == "egress":
        return EgressPolicyRevisionCreate(
            **common,
            allowedSchemes=["https"],
            allowedHosts=["api.agnes-ai.cn"],
            allowedPorts=[443],
            regionState="confirmed",
            region="isolated-cn",
        )
    return DataClassificationPolicyRevisionCreate(
        **common,
        allowedClassifications=["public_catalog"],
        prohibitedClassifications=[
            "direct_pii",
            "raw_order_detail",
            "customer_conversation",
            "credential",
            "commercial_sensitive",
            "cross_tenant",
            "unknown",
        ],
    )


def signed_case(kind, sign):
    maker = f"synthetic-native-r1-maker-{uuid4().hex}"
    checker = f"synthetic-native-r1-checker-{uuid4().hex}"
    with exact_owner() as owner:
        for actor in (maker, checker):
            owner.execute(
                "INSERT INTO meta_membership(org_id,project_id,subject,role) "
                "VALUES(%s,%s,%s,'owner')",
                (*SCOPE.key, actor),
            )
    draft = candidate(kind)
    store = AipRuntimeGuardPolicyStore()
    publish = (
        store.publish_egress
        if kind == "egress"
        else store.publish_data_classification
    )
    published = publish(
        SCOPE, maker, f"synthetic-native-r1-draft-{uuid4().hex}", draft
    )
    create_type = (
        EgressPolicyRevisionCreate
        if kind == "egress"
        else DataClassificationPolicyRevisionCreate
    )
    active = create_type.model_validate(
        {
            **draft.model_dump(mode="json", by_alias=True),
            "revision": 2,
            "lifecycle": "active",
        }
    )
    command = GuardMakerCommand(
        orgId=SCOPE.org_id,
        projectId=SCOPE.project_id,
        bearerToken=sign(maker),
        candidate=active,
        expectedVersion=published.revision,
        idempotencyKey=f"synthetic-native-r1-propose-{uuid4().hex}",
        expiresAt=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    return maker, checker, propose_guard_signed(command)


def decision(sign, actor, bundle):
    return GuardDecisionCommand(
        orgId=SCOPE.org_id,
        projectId=SCOPE.project_id,
        bearerToken=sign(actor),
        proposalId=bundle.proposal.id,
        idempotencyKey=f"synthetic-native-r1-decision-{uuid4().hex}",
        decision=DecideActionProposalRequest(
            expectedProposalVersion=bundle.proposal.version,
            expectedProposalHash=bundle.proposal.proposal_hash,
            decision="approved",
            reason="synthetic isolated native r1 matrix only",
            approvalExpiresAt=datetime.now(timezone.utc) + timedelta(minutes=3),
        ),
    )


@pytest.mark.parametrize("kind", ["egress", "data_classification"])
def test_native_positive_and_at_most_once(
    kind, https_signer, issuer_connection
):
    sign, _requests = https_signer
    _maker, checker, bundle = signed_case(kind, sign)
    factory, state = issuer_connection
    attempts = state / f"positive-{kind}"
    attempts.mkdir(mode=0o700)
    issuer = GuardPolicyIssuer(
        factory, attempts, expected_database=EXPECTED_DATABASE
    )
    command = decision(sign, checker, bundle)
    result = issuer.execute(command)
    assert result["status"] == "observed"
    assert result["decision"] == "approved"
    assert result["activationAuthorized"] is False
    assert issuer.execute(command) == result
    assert issuer.inquire(command) == result
    assert len(list(attempts.iterdir())) == 1


@pytest.mark.parametrize(
    "bad", ["self", "revoked", "wrong_signature", "cross_tenant"]
)
def test_native_invalid_authority_never_attempts(
    bad, https_signer, issuer_connection
):
    sign, _requests = https_signer
    maker, checker, bundle = signed_case("egress", sign)
    command = decision(sign, maker if bad == "self" else checker, bundle)
    if bad == "revoked":
        with exact_owner() as owner:
            owner.execute(
                "DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s "
                "AND subject=%s",
                (*SCOPE.key, checker),
            )
    elif bad == "wrong_signature":
        command.bearer_token = SecretStr(sign(checker, wrong_key=True))
    elif bad == "cross_tenant":
        command.bearer_token = SecretStr(
            sign(checker, changes={"org_id": "dev-org"})
        )
    factory, state = issuer_connection
    attempts = state / f"negative-{bad}"
    attempts.mkdir(mode=0o700)
    with pytest.raises(GuardIssuerBlocked):
        GuardPolicyIssuer(
            factory, attempts, expected_database=EXPECTED_DATABASE
        ).execute(command)
    assert list(attempts.iterdir()) == []


@pytest.mark.parametrize("when", ["before_commit", "after_commit"])
def test_native_unknown_is_never_reexecuted(
    when, https_signer, issuer_connection
):
    sign, _requests = https_signer
    _maker, checker, bundle = signed_case("egress", sign)
    base, state = issuer_connection
    write_calls = []

    @contextmanager
    def faulty(scope, read_only):
        if not read_only:
            write_calls.append(True)
        decision_call = not read_only and len(write_calls) == 2
        with base(scope, read_only) as conn:
            yield conn
            if decision_call and when == "before_commit":
                raise ConnectionError("synthetic loss before commit")
        if decision_call and when == "after_commit":
            raise ConnectionError("synthetic loss after commit")

    attempts = state / f"unknown-{when}"
    attempts.mkdir(mode=0o700)
    issuer = GuardPolicyIssuer(
        faulty, attempts, expected_database=EXPECTED_DATABASE
    )
    command = decision(sign, checker, bundle)
    first = issuer.execute(command)
    assert first["status"] == (
        "observed" if when == "after_commit" else "unresolved"
    )
    assert issuer.execute(command) == first
    assert issuer.inquire(command) == first
    assert len(list(attempts.iterdir())) == 1


def test_native_runtime_cannot_impersonate_private_issuer(
    https_signer, issuer_connection
):
    sign, _requests = https_signer
    _maker, checker, bundle = signed_case("egress", sign)

    @contextmanager
    def wrong_factory(scope, read_only):
        with connect(scope) as conn:
            yield conn

    _factory, state = issuer_connection
    attempts = state / "negative-runtime-impersonation"
    attempts.mkdir(mode=0o700)
    with pytest.raises(GuardIssuerBlocked, match="DATABASE_IDENTITY"):
        GuardPolicyIssuer(
            wrong_factory, attempts, expected_database=EXPECTED_DATABASE
        ).execute(decision(sign, checker, bundle))
    assert list(attempts.iterdir()) == []
