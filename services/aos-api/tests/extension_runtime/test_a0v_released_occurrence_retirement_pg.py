"""A0-V released-runtime fence and per-occurrence unaccepted retirement."""
from pathlib import Path
from uuid import uuid4

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import _migration
from test_event_control_dispatch_lifecycle_pg import _request, _transition
from test_released_event_control_retirement_pg import _released
from test_unaccepted_analysis_closure_pg import closure_db, close


pytest_plugins = (
    "test_ecommerce_growth_cutover_pg",
    "test_event_control_dispatch_lifecycle_pg",
)


pytestmark = pytest.mark.skipif(
    __import__("os").getenv("AOS_EXTENSION_PG_TEST") != "1",
    reason="isolated PG required",
)


@pytest.fixture
def released_closure_db(closure_db):
    root = Path(__file__).resolve().parents[2]
    _migration(root, "a0v_074_released_event_control_retirement.py", closure_db.owner,
               schema=closure_db.schema)
    _migration(root, "a0v_076_released_occurrence_retirement.py", closure_db.owner,
               schema=closure_db.schema)
    return closure_db


def _occurrence(db, scope, ids, *, execution_epoch, status, source_event):
    occurrence = str(uuid4())
    db.owner.execute(
        """INSERT INTO automation_occurrence(org_id,project_id,occurrence_id,policy_id,
        policy_revision,policy_hash,operation_id,installation_id,generation,execution_epoch,
        trigger_source,source_event_id,status,deadline) VALUES(%s,%s,%s,'product-change-current',1,
        %s,'ecommerce_growth_analysis_advance',%s,%s,%s,'event',%s,%s,
        clock_timestamp()-interval '1 minute')""",
        (*scope.key, occurrence, "sha256:" + "a" * 64, ids[0], ids[1], execution_epoch,
         source_event, status),
    )
    target = f"automation-occurrence:{occurrence}"
    if status == "needs_attention":
        db.owner.execute(
            """INSERT INTO automation_occurrence_dispatch_attempt(org_id,project_id,attempt_id,
            occurrence_id,claim_owner,target_idempotency_key,status,claimed_at,claim_until)
            VALUES(%s,%s,%s,%s,'worker',%s,'unknown',clock_timestamp()-interval '2 minutes',
            clock_timestamp()-interval '1 minute')""",
            (*scope.key, uuid4(), occurrence, target),
        )
    origin = dict(orgId=scope.org_id, projectId=scope.project_id, occurrenceId=occurrence,
                  sourceEventId=source_event, runId=f"source-{source_event[:8]}",
                  actor="fixture-operator")
    db.owner.execute(
        """INSERT INTO ecommerce_product_event_origin(org_id,project_id,occurrence_id,
        source_event_id,run_id,actor,content_hash) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
        (*scope.key, occurrence, source_event, origin["runId"], origin["actor"],
         canonical_sha256(origin)),
    )
    return occurrence, target


def _released_with_occurrences(db):
    scope = TenantScope("org-org", "dev-project")
    ids, installation_revision, group_revision, event_epoch = _released(db, scope)
    db.owner.execute(
        """INSERT INTO automation_schedule_binding(org_id,project_id,policy_id,policy_revision,
        policy_hash,operation_id,installation_id,generation,execution_epoch,timezone,cadence,
        effective_from,approved,enabled) VALUES(%s,%s,'product-change-current',1,%s,
        'ecommerce_growth_analysis_advance',%s,%s,%s,'Asia/Shanghai','event',
        clock_timestamp()-interval '1 hour',true,false)""",
        (*scope.key, "sha256:" + "a" * 64, ids[0], ids[1], event_epoch),
    )
    unknown = _occurrence(db, scope, ids, execution_epoch=event_epoch,
                          status="needs_attention", source_event="e" * 64)
    pending = _occurrence(db, scope, ids, execution_epoch=event_epoch,
                          status="pending", source_event="f" * 64)
    fence = _request(ids, "fence", group_revision, "released-occurrence-fence")
    fence["installationRef"]["revision"] = installation_revision
    fence["executionEpoch"] = event_epoch
    fence["runtimeRevision"] = 7
    return scope, ids, fence, unknown, pending


def _closure_request(occurrence, fence, key):
    return dict(schemaVersion="aos.ecommerce.unaccepted-analysis-closure/v1",
                occurrenceId=occurrence, fenceReceiptId=fence["receiptId"],
                fenceContentHash=fence["contentHash"], idempotencyKey=key)


def test_released_fence_then_closes_expired_unknown_and_unclaimed_pending(released_closure_db):
    db = released_closure_db
    scope, _, fence_request, unknown, pending = _released_with_occurrences(db)
    fence = _transition(db, scope, fence_request)
    assert fence["releasedRuntimeRecovery"] is True
    precondition = db.owner.execute(
        """SELECT o.status,o.trigger_source,o.operation_id,o.receipt_ref,
        o.installation_id::text AS occurrence_installation,o.generation::text AS occurrence_generation,
        o.execution_epoch AS occurrence_epoch,o.policy_id AS occurrence_policy,
        r.installation_id::text AS fence_installation,r.generation::text AS fence_generation,
        r.execution_epoch AS fence_epoch,r.policy_id AS fence_policy
        FROM automation_occurrence o CROSS JOIN extension_event_control_dispatch_receipt r
        WHERE o.occurrence_id=%s AND r.receipt_id=%s""",
        (unknown[0], fence["receiptId"]),
    ).fetchone()
    assert precondition == {
        "status": "needs_attention", "trigger_source": "event",
        "operation_id": "ecommerce_growth_analysis_advance", "receipt_ref": None,
        "occurrence_installation": fence["installationRef"]["installationId"],
        "occurrence_generation": fence["generation"], "occurrence_epoch": fence["executionEpoch"],
        "occurrence_policy": fence["schedulePolicyId"],
        "fence_installation": fence["installationRef"]["installationId"],
        "fence_generation": fence["generation"], "fence_epoch": fence["executionEpoch"],
        "fence_policy": fence["schedulePolicyId"],
    }
    unknown_receipt = close(db, scope, _closure_request(unknown[0], fence, "close-unknown"))
    pending_receipt = close(db, scope, _closure_request(pending[0], fence, "close-pending"))
    assert unknown_receipt["closureMode"] == "expired_unknown"
    assert pending_receipt["closureMode"] == "pending_unclaimed"
    assert pending_receipt["priorAttempt"] is None
    assert pending_receipt["targetEvidence"]["targetIdempotencyKey"] == pending[1]
    assert close(db, scope, _closure_request(pending[0], fence, "close-pending"))["replayed"] is True
    assert db.owner.execute(
        "SELECT count(*) AS n FROM automation_occurrence WHERE status='cancelled'"
    ).fetchone()["n"] == 2
    assert db.owner.execute(
        "SELECT count(*) AS n FROM automation_occurrence_dispatch_attempt "
        "WHERE status='closed_unaccepted'"
    ).fetchone()["n"] == 1
    assert db.owner.execute(
        "SELECT count(*) AS n FROM ecommerce_unaccepted_analysis_closure_receipt"
    ).fetchone()["n"] == 2


@pytest.mark.parametrize("fault", ["future", "target", "claimed"])
def test_released_fence_rejects_unsafe_unknown(released_closure_db, fault):
    db = released_closure_db
    scope, _, fence_request, unknown, _ = _released_with_occurrences(db)
    if fault == "future":
        db.owner.execute(
            "UPDATE automation_occurrence_dispatch_attempt SET claim_until=clock_timestamp()+interval '1 hour' "
            "WHERE occurrence_id=%s", (unknown[0],),
        )
    elif fault == "target":
        db.owner.execute(
            "INSERT INTO ecommerce_growth_runtime_command_receipt VALUES(%s,%s,%s,%s)",
            (*scope.key, "ecommerce_growth_analysis_advance", unknown[1]),
        )
    else:
        db.owner.execute(
            "UPDATE automation_occurrence_dispatch_attempt SET status='claimed' WHERE occurrence_id=%s",
            (unknown[0],),
        )
    with pytest.raises(Exception, match="event dispatch runtime drifted"):
        _transition(db, scope, fence_request)
    assert db.owner.execute(
        "SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE phase='fence'"
    ).fetchone()["n"] == 0
