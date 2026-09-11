"""Trusted internal receiver for completed D03 growth-plan proposals.

No public route and no Provider invocation. Scope, markings and workflow settings
must come from the authorized server workflow, not an unvalidated client body.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from hashlib import sha256

from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
from aos_api.ecommerce_analyst_growth_plan_sources import require_growth_plan_sources
from aos_api.tenant_scope import TenantScope


class GrowthPlanDraftReceiver:
    def __init__(self, connect_factory):
        if not callable(connect_factory):
            raise ValueError("explicit scoped connection factory required")
        self._connect_factory = connect_factory

    def receive(self, scope: TenantScope, *, attempt_id: str, decision_ref: AnalystExactRef,
                answer: str, budget: str, task_type: str, actor: str, markings: list[str],
                now: datetime, max_source_age: timedelta) -> AnalystExactRef:
        if not actor.strip() or decision_ref.resource_type != "DecisionSummaryRevision":
            raise ValueError("actor and exact decision required")
        if not isinstance(answer, str) or len(answer.encode("utf-8")) > 131072:
            raise ValueError("bounded answer required")
        identity = canonical_hash({"tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                                   "attemptId": attempt_id})
        key = "growth-draft-receive:" + identity
        with self._connect_factory(scope) as conn:
            # The existing Owner commits only after all validations and inserts.
            # Do not place this inside conn.transaction(): Owner owns the commit.
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))

            @contextmanager
            def bound(requested_scope):
                if requested_scope != scope:
                    raise ValueError("transaction scope mismatch")
                yield conn

            attempt = AipAgentRunExecutionService(bound).get(scope, attempt_id)
            if ((attempt.tenant.org_id, attempt.tenant.project_id) != scope.key
                    or attempt.attempt_id != attempt_id or attempt.status != "succeeded"
                    or not attempt.completed_at or not attempt.provider_receipt_id
                    or not attempt.usage_receipt_ids or attempt.reason_code is not None):
                raise ValueError("successful scoped generation required")
            artifact = attempt.output_artifact_ref
            if (artifact is None or artifact.artifact_type != "agent_text_output" or artifact.revision != "1"
                    or artifact.content_hash != sha256(answer.encode("utf-8")).hexdigest()):
                raise ValueError("exact original answer artifact required")
            run = AipAgentRunService(bound).get(scope, attempt.agent_run_id)
            if ((run.tenant.org_id, run.tenant.project_id) != scope.key
                    or run.agent_run_id != attempt.agent_run_id
                    or run.request.skill.asset_type != "SkillTemplate"
                    or run.request.skill.asset_id != "ecommerce.skill.D03"
                    or run.request.model_route != attempt.route_ref or run.request.policy != attempt.policy_ref):
                raise ValueError("generation does not belong to the scoped D03 workflow")
            row = conn.execute(
                """SELECT run_id,artifact_type,content_hash,content_ref,source FROM aip_artifact
                WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
                (*scope.key, artifact.artifact_id),
            ).fetchone()
            if (row is None or row["run_id"] != run.task_run_id or row["artifact_type"] != "agent_text_output"
                    or row["content_hash"] != artifact.content_hash
                    or row["content_ref"] != "sha256://" + artifact.content_hash
                    or not isinstance(row["source"], dict)
                    or row["source"].get("agentRunId") != run.agent_run_id
                    or row["source"].get("attemptId") != attempt.attempt_id):
                raise ValueError("persisted generation artifact mismatch")
            owner = EcommerceAnalystAuthorityStore(bound)
            replay_ref = owner.find_plan_publication_receipt(scope, key)
            if replay_ref is not None:
                old = owner.get_plan_exact(scope, replay_ref)
                expected_artifact = AnalystExactRef(resourceType="Artifact", resourceId=artifact.artifact_id,
                                                   revision=1, contentHash=artifact.content_hash)
                if (old.created_by != actor or old.decision_ref != decision_ref or old.budget != budget
                        or any(item.task_type != task_type for item in old.items)
                        or old.generation_artifact_ref != expected_artifact
                        or old.lifecycle != "draft" or old.revision != 1
                        or canonical_hash(old.model_dump(mode="json", by_alias=True, exclude={"content_hash"})) != old.content_hash):
                    raise ValueError("generation replay command drifted")
                return replay_ref
            decision = require_growth_plan_sources(conn, scope, decision_ref, markings=markings,
                                                    now=now, max_source_age=max_source_age)
            inputs = {(ref.resource_type, ref.resource_id, ref.revision, ref.authority)
                      for ref in run.request.input_refs}
            required = {(ref.resource_type, ref.resource_id, str(ref.revision), "postgresql")
                        for ref in [decision_ref, decision.insight_ref, *decision.evidence_refs]}
            if not required.issubset(inputs):
                raise ValueError("D03 run did not declare exact planning inputs")
            draft = draft_from_completed_generation(decision=decision, attempt=attempt, answer=answer,
                                                    budget=budget, task_type=task_type, actor=actor)
            return owner.publish_plan(scope, actor, key, draft, expected_version=0)
