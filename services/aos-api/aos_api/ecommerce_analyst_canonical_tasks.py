"""Original TaskStore adapter for the existing Analyst TaskGraph orchestrator."""
from copy import deepcopy
from hashlib import sha256

from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore, _canonical_hash
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef


def task_creation_ref(row, expected=None):
    if row is None:
        raise ValueError("canonical Task creation record is missing")
    payload = dict(type=row["task_type"], title=row["title"], description=row["description"],
                   priority=row["priority"], goal=row["goal"],
                   selectionRef=row["selection_ref"], policyRevision=row["policy_revision"])
    if (expected is not None and payload != expected) or _canonical_hash(payload) != row["request_hash"] or row["version"] < 1:
        raise ValueError("canonical Task creation content drifted")
    return AnalystExactRef(resourceType="Task", resourceId=row["task_id"], revision=1,
                           contentHash=row["request_hash"])


class OriginalCanonicalTaskMaterializer:
    def __init__(self, connect_factory, source_context, *, tasks=None):
        self._connect = connect_factory
        self._source = deepcopy(source_context)
        self._tasks = tasks or AipTaskStore(connect_factory)

    def materialize_exact_tasks(self, scope, actor, key, requests):
        if len({item.plan_item_id for item in requests}) != len(requests):
            raise ValueError("duplicate eligible plan item")
        result = {}
        for item in requests:
            item_key = key + ":" + sha256(item.plan_item_id.encode()).hexdigest()[:24]
            goal = {**item.goal, "planItemId": item.plan_item_id,
                    "materialization": deepcopy(self._source),
                    "workshopAssignment": deepcopy(self._source["assignment"])}
            body = CreateTaskRequest(type=item.task_type, title=item.title,
                                     description=item.goal["objective"], priority=item.priority, goal=goal)
            with self._connect(scope) as conn:
                row = conn.execute("SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                                   (*scope.key, item_key)).fetchone()
            if row is None:
                self._tasks.create_task(scope, actor, item_key, body)
                with self._connect(scope) as conn:
                    row = conn.execute("SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                                       (*scope.key, item_key)).fetchone()
            result[item.plan_item_id] = task_creation_ref(row, body.model_dump(mode="json", by_alias=True))
        return result
