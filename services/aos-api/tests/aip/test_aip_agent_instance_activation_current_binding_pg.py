"""Current Binding evidence must survive through the Agent activation commit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import psycopg
from psycopg.conninfo import conninfo_to_dict

from aos_api.aip_agent_control_contracts import ActivateAgentInstanceRequest
from aos_api.aip_agent_instance_activation_service import AipAgentInstanceActivationService
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryStore, AipAgentRegistryTransitionBlocked,
)
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _prerequisites(now):
    database = conninfo_to_dict(get_dsn())["dbname"]
    assert database.startswith("aos_test_") and database.endswith("_ti4_test")
    suffix = uuid4().hex
    template_id, instance_id, binding_id = (
        f"s3owag-template-{suffix}", f"s3owag-agent-{suffix}",
        f"s3owag-binding-{suffix}",
    )
    with connect(SCOPE) as conn:
        conn.execute("""INSERT INTO aip_agent_template_revision
            (template_id,revision,display_name,role_key,lifecycle,source_ref,
             source_license,manifest,content_hash,created_by)
            VALUES(%s,1,'S3OWAG','tester','published','{}','internal','{}',%s,'test-only')""",
            (template_id, "a" * 64))
        conn.execute("""INSERT INTO aip_agent_instance
            (org_id,project_id,instance_id,template_id,template_revision,status,
             overlay,version,created_by)
            VALUES(%s,%s,%s,%s,1,'provisioning','{}',1,'test-only')""",
            (*SCOPE.key, instance_id, template_id))
        conn.execute("""INSERT INTO aip_capability_binding
            (org_id,project_id,binding_id,capability_ref,secret_ref,health,
             network_policy_revision,quota_policy_revision,timeout_ms,max_concurrency,
             status,operational_readiness,dependency_snapshot_hash,
             last_evaluated_at,readiness_expires_at)
            VALUES(%s,%s,%s,'{}','secret://test-only','healthy','test-only',
                   'test-only',1000,1,'active','available',%s,%s,%s)""",
            (*SCOPE.key, binding_id, "b" * 64, now, now + timedelta(minutes=10)))
        conn.commit()
    return instance_id, binding_id


def _activate(store, instance_id, binding_id, now):
    return AipAgentInstanceActivationService(store=store).activate(
        SCOPE, instance_id,
        ActivateAgentInstanceRequest(expected_version=1,
                                     capability_binding_ids=[binding_id]),
        idempotency_key=f"s3owag-activate-{instance_id}", actor="test-only",
        occurred_at=now,
    )


def test_binding_revoked_after_preflight_cannot_activate_or_issue_receipt():
    now = datetime.now(UTC)
    instance_id, binding_id = _prerequisites(now)

    class RevokingStore(AipAgentRegistryStore):
        def update_instance(self, scope, target, request, **kwargs):
            with connect(scope) as conn:
                conn.execute("""UPDATE aip_capability_binding SET status='revoked'
                    WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                    (*scope.key, binding_id))
                conn.commit()
            return super().update_instance(scope, target, request, **kwargs)

    with pytest.raises(AipAgentRegistryTransitionBlocked,
                       match="fresh active CapabilityBinding"):
        _activate(RevokingStore(), instance_id, binding_id, now)
    with connect(SCOPE) as conn:
        assert conn.execute("""SELECT status FROM aip_agent_instance WHERE
            org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, instance_id)).fetchone()["status"] == "provisioning"
        assert conn.execute("""SELECT count(*) AS n FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s AND operation='agent_instance.update'
              AND result_ref->>'resourceId'=%s""",
            (*SCOPE.key, instance_id)).fetchone()["n"] == 0


def test_current_binding_activates_with_original_registry_receipt():
    now = datetime.now(UTC)
    instance_id, binding_id = _prerequisites(now)
    instance, receipt = _activate(AipAgentRegistryStore(), instance_id, binding_id, now)
    assert instance.status.value == "active"
    assert receipt.operation == "agent_instance.update"
    assert receipt.result_ref.resource_id == instance_id


def test_binding_expired_before_write_transaction_cannot_activate():
    old_admission_time = datetime.now(UTC) - timedelta(minutes=20)
    instance_id, binding_id = _prerequisites(old_admission_time)
    # The prerequisite snapshot was valid at admission but expired ten minutes
    # before this write transaction.  Receipt time is not a freshness clock.
    with pytest.raises(AipAgentRegistryTransitionBlocked,
                       match="fresh active CapabilityBinding"):
        _activate(AipAgentRegistryStore(), instance_id, binding_id,
                  old_admission_time)
    with connect(SCOPE) as conn:
        assert conn.execute("""SELECT status FROM aip_agent_instance WHERE
            org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, instance_id)).fetchone()["status"] == "provisioning"
        assert conn.execute("""SELECT count(*) AS n FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s AND operation='agent_instance.update'
              AND result_ref->>'resourceId'=%s""",
            (*SCOPE.key, instance_id)).fetchone()["n"] == 0


def test_binding_lock_blocks_concurrent_revoke_until_activation_commits():
    now = datetime.now(UTC)
    instance_id, binding_id = _prerequisites(now)

    class LockProbeStore(AipAgentRegistryStore):
        def update_instance(self, scope, target, request, **kwargs):
            if "before_update" not in kwargs:
                return super().update_instance(scope, target, request, **kwargs)
            check = kwargs["before_update"]

            def check_and_probe(conn):
                check(conn)
                with connect(scope) as other:
                    other.execute("SET lock_timeout='200ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        other.execute("""UPDATE aip_capability_binding SET status='revoked'
                            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
                            (*scope.key, binding_id))

            kwargs["before_update"] = check_and_probe
            return super().update_instance(scope, target, request, **kwargs)

    store = LockProbeStore()
    _, receipt = _activate(store, instance_id, binding_id, now)
    with connect(SCOPE) as conn:
        conn.execute("""UPDATE aip_capability_binding SET status='revoked'
            WHERE org_id=%s AND project_id=%s AND binding_id=%s""",
            (*SCOPE.key, binding_id))
        conn.commit()
    replayed, replay_receipt = _activate(store, instance_id, binding_id, now)
    assert replayed.status.value == "active"
    assert replay_receipt.receipt_id == receipt.receipt_id
