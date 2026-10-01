"""Existing-policy rows for read-path tests in pytest's disposable PostgreSQL."""

import json

from aos_api.aip_model_governance_policy_contracts import QuotaPolicyRevisionCreate
from aos_api.aip_model_governance_policy_store import materialize_policy
from aos_api.db import connect


def seed_historical_model_policy(scope, actor, item):
    if type(item) is QuotaPolicyRevisionCreate:
        from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard
        return seed_historical_runtime_guard(scope,actor,item)
    policy = materialize_policy(scope, actor, item)
    kind = "quota" if isinstance(item, QuotaPolicyRevisionCreate) else "budget"
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_model_governance_policy_head
               (org_id,project_id,policy_kind,policy_id,current_revision,version)
               VALUES(%s,%s,%s,%s,%s,1)""",
            (*scope.key, kind, policy.policy_id, policy.revision),
        )
        conn.execute(
            """INSERT INTO aip_model_governance_policy_revision
               (org_id,project_id,policy_kind,policy_id,revision,content_hash,lifecycle,
                effective_from,effective_until,payload,created_by,created_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (*scope.key, kind, policy.policy_id, policy.revision, policy.content_hash,
             policy.lifecycle.value, policy.effective_from, policy.effective_until,
             json.dumps(policy.model_dump(mode="json", by_alias=True)), policy.created_by, policy.created_at),
        )
        conn.commit()
    return policy
