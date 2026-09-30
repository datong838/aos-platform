"""Real isolated Producer/Issuer -> SQL consumption, never live authorization."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier

import psycopg
import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.tenant_scope import TenantScope
from tests.aip.test_network_approval_precheck_expiry_pg import SCOPE, _approved
from tests.aip.test_network_consumer_boundary_pg import isolated_owner


@contextmanager
def consumer(scope=SCOPE):
    with isolated_owner() as conn:
        conn.execute("SET SESSION AUTHORIZATION aos_network_consumer_call")
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)
        yield conn


def consume(conn, proposal, event, scope=SCOPE):
    return conn.execute("SELECT public.aip_consume_network_activation_a0v_120(%s,%s,%s,%s) AS result",
                        (*scope.key, proposal, event)).fetchone()["result"]


def counts(proposal):
    with isolated_owner() as conn:
        policy = conn.execute("SELECT payload->'candidate'->>'policyId' AS id FROM aip_action_proposal "
                              "WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                              (*SCOPE.key, proposal)).fetchone()["id"]
        result = [conn.execute("SELECT count(*) AS n FROM " + table +
                               " WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                               (*SCOPE.key, policy)).fetchone()["n"]
                  for table in ("aip_network_policy_head", "aip_network_policy_revision")]
        result.append(conn.execute("SELECT count(*) AS n FROM aip_network_policy_receipt WHERE org_id=%s "
                                   "AND project_id=%s AND operation='network_policy.activate' AND idempotency_key=%s",
                                   (*SCOPE.key, proposal)).fetchone()["n"])
        return tuple(result)


def test_exact_approved_network_is_consumed_once_and_readable_by_existing_store():
    proposal, event, _, _ = _approved(None)
    assert counts(proposal) == (0, 0, 0)
    with consumer() as conn:
        receipt = consume(conn, proposal, event)
    assert counts(proposal) == (1, 1, 1)
    assert receipt["proposalId"] == proposal and receipt["approvalEventId"] == event
    with consumer() as conn:
        assert consume(conn, proposal, event) == receipt
    assert counts(proposal) == (1, 1, 1)
    policy = AipNetworkPolicyStore().require_exact_active(SCOPE, VersionedAssetRef(
        assetType="NetworkPolicyRevision", assetId=receipt["resourceId"], revision=receipt["revision"],
        contentHash=receipt["contentHash"],
    ))
    assert policy.lifecycle.value == "active"


def test_concurrent_consumers_return_one_receipt():
    proposal, event, _, _ = _approved(None)
    start = Barrier(2)
    def worker():
        with consumer() as conn:
            conn.execute("SET LOCAL statement_timeout='10s'")
            start.wait(timeout=5)
            return consume(conn, proposal, event)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(worker), pool.submit(worker)
        assert a.result(timeout=15) == b.result(timeout=15)
    assert counts(proposal) == (1, 1, 1)


def test_outer_transaction_failure_rolls_back_head_revision_and_receipt():
    proposal, event, _, _ = _approved(None)
    with pytest.raises(psycopg.errors.DivisionByZero):
        with consumer() as conn:
            consume(conn, proposal, event)
            conn.execute("SELECT 1/0")
    assert counts(proposal) == (0, 0, 0)
    with consumer() as conn:
        consume(conn, proposal, event)
    assert counts(proposal) == (1, 1, 1)


@pytest.mark.parametrize("case,reason", [
    ("scope", "SCOPE_IDENTITY_REQUIRED"),
    ("tenant", "PROPOSAL_UNAVAILABLE"),
    ("event", "APPROVAL_INVALID"),
    ("member", "CURRENT_MEMBER_REQUIRED"),
])
def test_invalid_current_authority_leaves_no_consumption(case, reason):
    proposal, event, checker, _ = _approved(None)
    other = TenantScope("isolated-other-org", "dev-project")
    if case == "member":
        with isolated_owner() as conn:
            conn.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                         (*SCOPE.key, checker))
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match=reason):
        with consumer(other if case == "tenant" else SCOPE) as conn:
            consume(conn, proposal, "missing-event" if case == "event" else event,
                    other if case in ("scope", "tenant") else SCOPE)
    assert counts(proposal) == (0, 0, 0)


def test_changed_event_cannot_reuse_completed_receipt():
    proposal, event, _, _ = _approved(None)
    with consumer() as conn:
        original = consume(conn, proposal, event)
    with pytest.raises(psycopg.errors.CheckViolation, match="RECEIPT_CONFLICT"):
        with consumer() as conn:
            consume(conn, proposal, "different-event")
    with consumer() as conn:
        assert consume(conn, proposal, event) == original
    assert counts(proposal) == (1, 1, 1)


@pytest.mark.parametrize("role", ["aos_runtime", "aos_network_approval_issuer"])
def test_other_authorities_cannot_execute_consumer(role):
    from psycopg import sql
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="permission denied for function"):
        with isolated_owner() as conn:
            conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(role)))
            consume(conn, "missing-proposal", "missing-event")


@pytest.mark.parametrize("expiring", ["proposal", "approval"])
def test_consumer_rechecks_expiry_after_real_member_lock_wait(expiring):
    import time
    import uuid
    proposal, event, checker, expires = _approved(expiring)
    application = "bg00ej-" + uuid.uuid4().hex
    with isolated_owner() as blocker:
        blocker.execute("SELECT 1 FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR UPDATE",
                        (*SCOPE.key, checker))
        def attempt():
            with consumer() as conn:
                conn.execute("SELECT set_config('application_name',%s,true)", (application,))
                conn.execute("SET LOCAL statement_timeout='10s'")
                return consume(conn, proposal, event)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(attempt)
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    blocker.execute("SELECT pg_stat_clear_snapshot()")
                    row = blocker.execute("SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",
                                          (application,)).fetchone()
                    if row and row["wait_event_type"] == "Lock":
                        break
                    time.sleep(.02)
                else:
                    raise AssertionError("consumer did not reach real lock wait")
                now = blocker.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
                assert now < expires
                blocker.execute("SELECT pg_sleep(%s)", ((expires-now).total_seconds()+.05,))
            finally:
                blocker.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match="NETWORK_CONSUMER_EXPIRED"):
                future.result(timeout=12)
    assert counts(proposal) == (0, 0, 0)


@pytest.mark.parametrize("mutation,reason", [
    ("withdrawal", "WITHDRAWN"), ("head", "HEAD_DRIFT"), ("egress", "EGRESS_DRIFT"),
])
def test_persisted_dependency_drift_refuses_consumption(mutation, reason):
    proposal, event, _, _ = _approved(None)
    with isolated_owner() as conn:
        row = conn.execute("SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s",
                           (*SCOPE.key, proposal)).fetchone()
        if mutation == "withdrawal":
            conn.execute("INSERT INTO aip_action_withdrawal_event(org_id,project_id,withdrawal_event_id,proposal_id,"
                         "proposal_version,proposal_hash,actor_id,reason,idempotency_key,request_hash) "
                         "VALUES(%s,%s,%s,%s,%s,%s,%s,'isolated withdrawal',%s,%s)",
                         (*SCOPE.key, proposal, proposal, row["version"], row["proposal_hash"],
                          row["created_by"], proposal, "a"*64))
        elif mutation == "head":
            conn.execute("INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
                         "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, row["payload"]["candidate"]["policyId"]))
        else:
            conn.execute("UPDATE aip_runtime_guard_policy_head SET current_revision=current_revision+1 "
                         "WHERE org_id=%s AND project_id=%s AND policy_kind='egress' AND policy_id=%s",
                         (*SCOPE.key, row["payload"]["candidate"]["egressPolicyRef"]["assetId"]))
    before = counts(proposal)
    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.CheckViolation), match=reason):
        with consumer() as conn:
            consume(conn, proposal, event)
    assert counts(proposal) == before
    assert before[1:] == (0, 0)


def test_migration_rejects_unreconciled_historical_network_approval():
    import importlib.util
    from pathlib import Path
    _approved(None)
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_120_network_atomic_consumer.py'
    spec = importlib.util.spec_from_file_location('network_atomic_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match='HISTORY_RECONCILIATION_REQUIRED'):
        with isolated_owner() as conn:
            conn.execute(migration.HISTORY_GATE_SQL)


@pytest.mark.parametrize('mutation', [
    'ALTER ROLE aos_network_consumer_call LOGIN',
    'GRANT aos_runtime TO aos_network_consumer_owner',
])
def test_migration_preflight_rejects_consumer_role_drift(mutation):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_120_network_atomic_consumer.py'
    spec = importlib.util.spec_from_file_location('network_atomic_preflight', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with isolated_owner() as conn:
        conn.execute(mutation)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='NETWORK_CONSUMER_ROLE_DRIFT'):
            conn.execute(migration.ROLE_PREFLIGHT_SQL)
        conn.rollback()
