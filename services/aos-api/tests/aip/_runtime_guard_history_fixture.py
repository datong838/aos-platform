"""Existing-policy rows for read-path tests in pytest's disposable PostgreSQL."""

import json

from aos_api.aip_runtime_guard_policy_store import materialize_policy
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.db import connect


def seed_historical_runtime_guard(scope, actor, item):
    policy = materialize_policy(scope, actor, item)
    kind = "egress" if isinstance(item, EgressPolicyRevisionCreate) else "data_classification"
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_runtime_guard_policy_head
               (org_id,project_id,policy_kind,policy_id,current_revision,version)
               VALUES(%s,%s,%s,%s,%s,1)""",
            (*scope.key, kind, policy.policy_id, policy.revision),
        )
        conn.execute(
            """INSERT INTO aip_runtime_guard_policy_revision
               (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                effective_from,effective_until,payload,created_by,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (*scope.key, kind, policy.policy_id, policy.revision, policy.content_hash,
             policy.lifecycle.value, policy.effective_from, policy.effective_until,
             json.dumps(policy.model_dump(mode="json", by_alias=True)), policy.created_by, policy.created_at),
        )
        conn.commit()
    return policy
