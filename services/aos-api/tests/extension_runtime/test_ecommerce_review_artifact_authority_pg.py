from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
    PlanStep,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect_serializable
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ReviewAdvanceHostService,
    TransactionBoundConnectFactory,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 9, 9, 8, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
FAMILIES = ("portrait", "diagnosis", "growth_plan", "evidence_summary")


def artifact_ref(family: str, *, artifact_id: str | None = None) -> dict[str, object]:
    return {
        "resourceType": "ArtifactRevision",
        "resourceId": artifact_id or f"review-{family}-artifact",
        "revision": 1,
        "contentHash": "sha256:" + HASH_A,
    }


def command() -> dict[str, object]:
    return {
        "artifactBindings": [
            {"family": family, "artifactRef": artifact_ref(family)}
            for family in FAMILIES
        ]
    }


def issue(artifact_id: str = "review-diagnosis-artifact"):
    return SimpleNamespace(
        artifact_ref=SimpleNamespace(artifact_id=artifact_id, content_hash=HASH_A)
    )


def create_run(transaction: HostTransaction) -> str:
    store = AipTaskStore(TransactionBoundConnectFactory(transaction, SCOPE))
    task = store.create_task(
        SCOPE,
        "user:reviewer",
        "review-artifact-task-1",
        CreateTaskRequest(title="Review Artifact authority"),
    )
    plan = store.create_plan(
        SCOPE,
        "user:reviewer",
        task.id,
        "review-artifact-plan-1",
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[PlanStep(step_key="review", title="Review")],
        ),
    )
    store.approve_plan(
        SCOPE,
        "user:reviewer",
        task.id,
        plan.revision,
        task.version + 1,
        plan.content_hash,
    )
    return store.create_run(
        SCOPE,
        "user:reviewer",
        task.id,
        "review-artifact-run-1",
        CreateTaskRunRequest(
            plan_revision_id=plan.id,
            expected_task_version=task.version + 2,
        ),
    ).id


@pytest.mark.parametrize("last_run_id", ["task-run-2", "", " task-run-1"])
def test_review_artifacts_reject_invalid_or_mixed_aip_task_runs(last_run_id):
    rows = [
        {
            "artifact_id": f"review-{family}-artifact",
            "run_id": last_run_id if family == "evidence_summary" else "task-run-1",
            "artifact_type": family,
            "content_hash": HASH_A,
            "family_revision": None,
        }
        for family in FAMILIES
    ]

    class Result:
        def fetchall(self):
            return rows

    class Transaction:
        def execute(self, _query, _params):
            return Result()

    with pytest.raises(ValueError, match="family authority|share one AIP TaskRun"):
        ReviewAdvanceHostService._revalidate_artifacts(
            transaction=Transaction(), scope=SCOPE, command=command(), issue=issue()
        )


def test_review_artifacts_require_public_exact_family_run_and_subject_and_roll_back():
    host = ReviewAdvanceHostService()
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        run_id = create_run(transaction)
        for family in FAMILIES:
            conn.execute(
                """INSERT INTO public.aip_artifact
                    (org_id,project_id,artifact_id,run_id,artifact_type,content_hash,
                     marking,created_by,created_at)
                    VALUES(%s,%s,%s,%s,%s,%s,'["internal"]'::jsonb,%s,%s)""",
                (
                    *SCOPE.key,
                    f"review-{family}-artifact",
                    run_id,
                    family,
                    HASH_A,
                    "user:reviewer",
                    NOW,
                ),
            )
        valid = command()
        host._revalidate_artifacts(
            transaction=transaction, scope=SCOPE, command=valid, issue=issue()
        )

        bad_hash = command()
        bad_hash["artifactBindings"][0]["artifactRef"]["contentHash"] = "sha256:" + HASH_B
        with pytest.raises(ValueError, match="exact authority"):
            host._revalidate_artifacts(
                transaction=transaction, scope=SCOPE, command=bad_hash, issue=issue()
            )
        bad_revision = command()
        bad_revision["artifactBindings"][0]["artifactRef"]["revision"] = 2
        with pytest.raises(ValueError, match="exact authority"):
            host._revalidate_artifacts(
                transaction=transaction, scope=SCOPE, command=bad_revision, issue=issue()
            )
        wrong_family = command()
        wrong_family["artifactBindings"][0]["family"] = "diagnosis"
        with pytest.raises(ValueError, match="family authority"):
            host._revalidate_artifacts(
                transaction=transaction, scope=SCOPE, command=wrong_family, issue=issue()
            )
        missing = command()
        missing["artifactBindings"][0]["artifactRef"] = artifact_ref(
            "portrait", artifact_id="missing-artifact"
        )
        with pytest.raises(ValueError, match="family authority"):
            host._revalidate_artifacts(
                transaction=transaction, scope=SCOPE, command=missing, issue=issue()
            )
        with pytest.raises(ValueError, match="subject is outside"):
            host._revalidate_artifacts(
                transaction=transaction,
                scope=SCOPE,
                command=valid,
                issue=issue("other-artifact"),
            )
        with pytest.raises(ValueError, match="family authority"):
            host._revalidate_artifacts(
                transaction=transaction, scope=CANARY, command=valid, issue=issue()
            )

        conn.execute("CREATE TEMP TABLE aip_artifact (LIKE public.aip_artifact INCLUDING DEFAULTS)")
        host._revalidate_artifacts(
            transaction=transaction, scope=SCOPE, command=valid, issue=issue()
        )

        conn.rollback()
        assert conn.execute(
            """SELECT count(*) AS n FROM public.aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id LIKE 'review-%%-artifact'""",
            SCOPE.key,
        ).fetchone()["n"] == 0
