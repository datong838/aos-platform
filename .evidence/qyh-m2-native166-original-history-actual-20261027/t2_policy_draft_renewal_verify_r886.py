"""Independent read-only verification for the four revision-2 policy drafts."""

from datetime import UTC, datetime
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


DSN = (
    "host=127.0.0.1 port=18458 dbname=aos_refresh_activation_native "
    "user=aos_refresh_activation_native_migrator connect_timeout=5 "
    "application_name=t2-policy-renewal-verify-r886"
)
UNTIL = datetime(2027, 3, 31, 4, 0, tzinfo=UTC)


def main():
    output = Path(os.environ["AOS_VERIFY_OUTPUT"])
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        with psycopg.connect(DSN, row_factory=dict_row) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SET ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true), set_config('aos.project_id','dev-project',true)")
            heads = [dict(row) for row in conn.execute("""
              SELECT 'budget' AS kind,budget_id AS resource_id,current_revision,version
                FROM aip_budget_head WHERE org_id='org-org' AND project_id='dev-project' AND budget_id='m2-three-t2-budget'
              UNION ALL
              SELECT policy_kind,policy_id,current_revision,version FROM aip_runtime_guard_policy_head
                WHERE org_id='org-org' AND project_id='dev-project' AND policy_id IN ('m2-three-t2-egress','m2-three-t2-data')
              UNION ALL
              SELECT policy_kind,policy_id,current_revision,version FROM aip_model_governance_policy_head
                WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='quota' AND policy_id='m2-three-t2-quota'
              ORDER BY kind
            """).fetchall()]
            revisions = [dict(row) for row in conn.execute("""
              SELECT 'budget' AS kind,budget_id AS resource_id,revision,lifecycle,effective_from,effective_until FROM aip_budget_revision
                WHERE org_id='org-org' AND project_id='dev-project' AND budget_id='m2-three-t2-budget'
              UNION ALL
              SELECT policy_kind,policy_id,revision,lifecycle,effective_from,effective_until FROM aip_runtime_guard_policy_revision
                WHERE org_id='org-org' AND project_id='dev-project' AND policy_id IN ('m2-three-t2-egress','m2-three-t2-data')
              UNION ALL
              SELECT policy_kind,policy_id,revision,lifecycle,effective_from,effective_until FROM aip_model_governance_policy_revision
                WHERE org_id='org-org' AND project_id='dev-project' AND policy_kind='quota' AND policy_id='m2-three-t2-quota'
              ORDER BY kind,revision
            """).fetchall()]
            receipt_count = conn.execute("""
              SELECT (SELECT count(*) FROM aip_budget_receipt WHERE idempotency_key LIKE 'm2-three-t2-renewal-20270331-%')
                   + (SELECT count(*) FROM aip_runtime_guard_policy_receipt WHERE idempotency_key LIKE 'm2-three-t2-renewal-20270331-%')
                   + (SELECT count(*) FROM aip_model_governance_policy_receipt WHERE idempotency_key LIKE 'm2-three-t2-renewal-20270331-%') AS n
            """).fetchone()["n"]
            refresh_count = conn.execute(
                "SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt"
            ).fetchone()["n"]
            active_count = sum(row["lifecycle"] == "active" for row in revisions)
            conn.execute("SELECT set_config('aos.org_id','dev-org',true), set_config('aos.project_id','dev-project',true)")
            negative_visible = conn.execute("""
              SELECT (SELECT count(*) FROM aip_budget_revision WHERE org_id='org-org' AND project_id='dev-project' AND budget_id='m2-three-t2-budget')
                   + (SELECT count(*) FROM aip_runtime_guard_policy_revision WHERE org_id='org-org' AND project_id='dev-project' AND policy_id IN ('m2-three-t2-egress','m2-three-t2-data'))
                   + (SELECT count(*) FROM aip_model_governance_policy_revision WHERE org_id='org-org' AND project_id='dev-project' AND policy_id='m2-three-t2-quota') AS n
            """).fetchone()["n"]
            conn.rollback()
        valid = (
            len(heads) == 4
            and all(row["current_revision"] == 2 and row["version"] == 2 for row in heads)
            and len(revisions) == 8
            and {row["revision"] for row in revisions} == {1, 2}
            and all(row["lifecycle"] == "draft" for row in revisions)
            and all(row["effective_until"] == UNTIL for row in revisions if row["revision"] == 2)
            and receipt_count == 4
            and active_count == 0
            and refresh_count == 0
            and negative_visible == 0
        )
        value = {
            "schema": "aos-t2-policy-draft-renewal-independent-readonly/v1",
            "verifiedAt": datetime.now(UTC).isoformat(),
            "valid": valid,
            "heads": heads,
            "revisions": revisions,
            "renewalReceiptCount": receipt_count,
            "activePolicyCount": active_count,
            "refreshReceiptCount": refresh_count,
            "devOrgPositiveRowsVisible": negative_visible,
            "databaseWrites": 0,
            "providerCalled": False,
        }
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    if not valid:
        raise SystemExit("independent renewal verification differs")


if __name__ == "__main__":
    main()
