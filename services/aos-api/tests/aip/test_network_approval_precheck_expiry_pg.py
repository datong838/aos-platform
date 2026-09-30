"""Real lock/time regression in pytest's disposable PG, not formal approval proof."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import os
import time
import uuid

import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_network_policy_action_producer import (
    decide_network_activation, propose_network_activation,
)
from aos_api.aip_network_policy_approval_consumer import (
    NetworkApprovalConsumptionBlocked, precheck_network_activation,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.auth import Principal
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard


SCOPE = TenantScope("org-org", "dev-project")


@contextmanager
def isolated_issuer(scope):
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        assert conn.info.dbname.startswith("aos_test_") and conn.info.dbname.endswith("_ti4_test")
        conn.execute("SET SESSION AUTHORIZATION aos_network_approval_issuer")
        # The store commits before reading its bundle. This disposable,
        # unpooled connection keeps its one scope across that commit.
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)", scope.key)
        yield conn


def _approved(expiring):
    assert os.environ.get("AOS_TEST_USE_SHARED_DATABASE") != "1"
    suffix = uuid.uuid4().hex[:10]
    maker, checker = f"bg00eh-maker-{suffix}", f"bg00eh-checker-{suffix}"
    with psycopg.connect(get_dsn(), row_factory=dict_row) as owner:
        assert owner.info.dbname.startswith("aos_test_") and owner.info.dbname.endswith("_ti4_test")
        owner.execute("INSERT INTO meta_org(id,name) VALUES(%s,'isolated test org') ON CONFLICT DO NOTHING",
                      (SCOPE.org_id,))
        owner.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES(%s,%s,'isolated test workspace') ON CONFLICT DO NOTHING",
                      SCOPE.key)
        for subject, role in ((maker, "owner"), (checker, "admin")):
            owner.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)",
                          (*SCOPE.key, subject, role))
    now = datetime.now(UTC)
    egress = seed_historical_runtime_guard(SCOPE, maker, EgressPolicyRevisionCreate(
        policyId=f"bg00eh-egress-{suffix}", revision=1, environment="development",
        allowedSchemes=["https"], allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block", regionState="confirmed",
        region="cn-test-only", effectiveFrom=now-timedelta(hours=1), effectiveUntil=now+timedelta(days=1),
        owner=maker, approvalRef="isolated-history-fixture", lifecycle="active",
    ))
    candidate = NetworkPolicyRevisionCreate(
        policyId=f"bg00eh-network-{suffix}", revision=1, allowedSchemes=["https"],
        allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443], tlsRequired=True,
        publicFallbackAllowed=False, egressPolicyRef={"assetType": "EgressPolicyRevision",
        "assetId": egress.policy_id, "revision": 1, "contentHash": egress.content_hash},
        effectiveFrom=now, effectiveUntil=now+timedelta(hours=1), owner=maker,
        approvalRef="isolated-test", lifecycle="active",
    )
    short = datetime.now(UTC)+timedelta(seconds=4)
    long = datetime.now(UTC)+timedelta(minutes=10)
    proposal = propose_network_activation(
        Principal(subject=maker, org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                  roles=["owner"], token_kind="oidc"), candidate, expected_version=0,
        idempotency_key=f"propose-{suffix}", expires_at=short if expiring == "proposal" else long,
    )
    approved = decide_network_activation(
        Principal(subject=checker, org_id=SCOPE.org_id, project_id=SCOPE.project_id,
                  roles=["admin"], token_kind="oidc"), proposal.proposal.id, f"approve-{suffix}",
        DecideActionProposalRequest.model_validate({
            "expectedProposalVersion": proposal.proposal.version,
            "expectedProposalHash": proposal.proposal.proposal_hash,
            "decision": "approved", "reason": "isolated real lock expiry proof",
            "approvalExpiresAt": (short if expiring else long).isoformat(),
        }), connect_factory=isolated_issuer,
    )
    return approved.proposal.id, approved.approvals[0].id, checker, short


def _network_counts(conn):
    return tuple(conn.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"]
                 for table in ("aip_network_policy_head", "aip_network_policy_revision", "aip_network_policy_receipt"))


def test_unexpired_precheck_does_not_write_network_policy():
    proposal, approval, _, _ = _approved(None)
    with connect(SCOPE) as conn:
        before = _network_counts(conn)
        proof = precheck_network_activation(conn, SCOPE, proposal, approval)
        assert proof.proposal_id == proposal and proof.approval_event_id == approval
        assert _network_counts(conn) == before


@pytest.mark.parametrize("expiring", ["proposal", "approval"])
def test_precheck_rejects_expiry_while_waiting_for_checker_lock(expiring):
    proposal, approval, checker, expires = _approved(expiring)
    application = f"bg00eh-{uuid.uuid4().hex}"
    with psycopg.connect(get_dsn(), row_factory=dict_row) as blocker:
        before = _network_counts(blocker)
        blocker.execute("SELECT 1 FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR UPDATE",
                        (*SCOPE.key, checker))

        def precheck():
            with connect(SCOPE) as conn:
                conn.execute("SELECT set_config('application_name',%s,true)", (application,))
                conn.execute("SET LOCAL statement_timeout='10s'")
                return precheck_network_activation(conn, SCOPE, proposal, approval)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(precheck)
            try:
                deadline = time.monotonic()+3
                while time.monotonic() < deadline:
                    waiting = blocker.execute("SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",
                                              (application,)).fetchone()
                    if waiting and waiting["wait_event_type"] == "Lock":
                        break
                    blocker.execute("SELECT pg_stat_clear_snapshot()")
                    time.sleep(.02)
                else:
                    raise AssertionError("precheck never reached real checker lock wait")
                now = blocker.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
                assert now < expires, "fixture expired before lock wait was observed"
                blocker.execute("SELECT pg_sleep(%s)", ((expires-now).total_seconds()+.05,))
                assert blocker.execute("SELECT clock_timestamp() AS now").fetchone()["now"] >= expires
            finally:
                blocker.rollback()
            with pytest.raises(NetworkApprovalConsumptionBlocked, match=f"{expiring.upper()}_EXPIRED"):
                future.result(timeout=12)
        assert _network_counts(blocker) == before
