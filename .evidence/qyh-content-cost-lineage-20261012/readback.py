"""Bounded current Qiyuehui lineage inventory, never admission or execution."""
import hashlib
import json
import sys
from pathlib import Path

import psycopg

sys.path[:0] = [
    "services/aos-api",
    ".evidence/qyh-source-boundary-rehearsal-20261011",
    ".evidence/qyh-full-system-restoration-20261011",
]
import real_contract as C
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

ROOT = Path(".evidence/qyh-content-cost-lineage-20261012")
OUT = ROOT / "result.json"
assert not OUT.exists(), "Reconcile existing result instead of overwriting"
QUERIES = {
    "taskRunStates": "SELECT status,count(*) AS count FROM aip_task_run WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status",
    "agentRunStates": "SELECT status,count(*) AS count FROM aip_agent_run WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status",
    "attemptStates": "SELECT status,count(*) AS count FROM aip_agent_run_execution_attempt WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status",
    "reservationStates": "SELECT state,count(*) AS count FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s GROUP BY state ORDER BY state",
    "proposalStates": "SELECT status,count(*) AS count,count(*) FILTER (WHERE activation_eligible AND expires_at>clock_timestamp()) AS current_eligible FROM aip_budget_cost_proposal WHERE org_id=%s AND project_id=%s GROUP BY status ORDER BY status",
    "decisionStates": "SELECT decision,count(*) AS count,count(*) FILTER (WHERE expires_at>clock_timestamp()) AS current_window FROM aip_budget_cost_decision WHERE org_id=%s AND project_id=%s GROUP BY decision ORDER BY decision",
    "costActivationReceipts": "SELECT count(*) AS count FROM aip_budget_receipt WHERE org_id=%s AND project_id=%s AND operation='budget_revision.activate_cost'",
    "costIssuerOperations": "SELECT operation,count(*) AS count FROM aip_budget_cost_issuer_receipt WHERE org_id=%s AND project_id=%s GROUP BY operation ORDER BY operation",
    "priceHeads": "SELECT count(*) AS count FROM aip_model_price_snapshot_head WHERE org_id=%s AND project_id=%s",
    "contentDraftArtifacts": "SELECT count(*) AS count FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_type='content_draft'",
    "contentDraftReceipts": "SELECT count(*) AS count FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='content_draft.register'",
    "agentTaskBinding": """SELECT count(*) AS agents,
        count(*) FILTER (WHERE t.run_id IS NULL) AS missing_task_run,
        count(*) FILTER (WHERE t.run_id IS NOT NULL AND (a.task_id<>t.task_id
          OR a.task_ref->>'resourceId'<>t.task_id
          OR a.task_run_ref->>'resourceId'<>t.run_id)) AS id_binding_drift,
        count(*) FILTER (WHERE a.status='running' AND t.status='running') AS both_running
        FROM aip_agent_run a LEFT JOIN aip_task_run t ON a.org_id=t.org_id
        AND a.project_id=t.project_id AND a.task_run_id=t.run_id
        WHERE a.org_id=%s AND a.project_id=%s""",
    "attemptBudgetReservation": """SELECT count(*) AS attempts,
        count(*) FILTER (WHERE EXISTS (SELECT 1 FROM aip_budget_reservation b
          WHERE b.org_id=e.org_id AND b.project_id=e.project_id
          AND b.task_ref->>'resourceId'=a.task_id
          AND b.policy_ref->>'resourceId'=e.budget_ref->>'assetId'
          AND b.policy_ref->>'revision'=e.budget_ref->>'revision'
          AND b.pricing_ref->>'resourceId'=e.price_snapshot_ref->>'assetId'
          AND b.pricing_ref->>'revision'=e.price_snapshot_ref->>'revision')) AS locator_matches_only
        FROM aip_agent_run_execution_attempt e LEFT JOIN aip_agent_run a
          ON e.org_id=a.org_id AND e.project_id=a.project_id AND e.agent_run_id=a.agent_run_id
        WHERE e.org_id=%s AND e.project_id=%s""",
}
assert all(q.lstrip().upper().startswith("SELECT") for q in QUERIES.values())
before = C.S.P.M.fingerprint("qyh-restored-pg-20261011")
metadata = C.S.D.metadata("qyh-restored-pg-20261011")
reads = []
for scope in [("org-org", "dev-project"), ("dev-org", "dev-project")]:
    with T.factory() as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        apply_asset_transaction_scope(conn, org_id=scope[0], project_id=scope[1])
        identity = conn.execute("""SELECT current_user AS role,current_database() AS db,
            system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly,
            current_setting('transaction_isolation') AS isolation,
            transaction_timestamp() AS snapshot_started_at FROM pg_control_system()""").fetchone()
        assert identity["role"] == "aos_runtime" and identity["db"] == "aos_meta_head"
        assert identity["cluster"] == "7695302940039200809"
        assert identity["readonly"] == "on" and identity["isolation"] == "repeatable read"
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_159"
        observed = {key: conn.execute(query, scope).fetchall() for key, query in QUERIES.items()}
        # A second read inside the same native snapshot must preserve exact row counts.
        # Clock-dependent current-window aggregates are deliberately excluded.
        for key in QUERIES.keys() - {"proposalStates", "decisionStates"}:
            assert conn.execute(QUERIES[key], scope).fetchall() == observed[key]
        reads.append({"scope": list(scope), "identity": identity, "observed": observed})
assert C.S.P.M.fingerprint("qyh-restored-pg-20261011") == before
assert C.S.D.metadata("qyh-restored-pg-20261011") == metadata
result = {
    "task": "qyh-content-cost-lineage-20261012", "authority": "AOS-001901",
    "reads": reads, "databaseWrites": 0, "current647DataAndMetadataUnchanged": True,
    "sourceHash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "locatorMatchesAreNotExactHashOrApprovalProof": True,
    "formalRestorationAccepted": False, "executionAuthorized": False,
}
with OUT.open("x") as handle:
    json.dump(result, handle, indent=2, default=str)
    handle.write("\n")
print(json.dumps({"reads": reads, "databaseWrites": 0}, default=str))
