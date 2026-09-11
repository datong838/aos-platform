"""Internal D02 recovery: retained original answer to a scoped diagnosis.

No Provider call or public route. Identity, markings and source grants must be
supplied by the authorized server workflow. Replays read historical results;
they do not renew authority for subsequent generation or execution.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json

from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_text_output import read_agent_text
from aos_api.ecommerce_analyst_analysis_sources import AnalysisBundleSourceRequest, read_analysis_bundle
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_diagnosis_generation import decision_from_completed_generation
from aos_api.ecommerce_analyst_growth_plan_sources import require_current_revision
from aos_api.tenant_scope import TenantScope


class DiagnosisReceiver:
    def __init__(self, connect_factory):
        if not callable(connect_factory):
            raise ValueError("explicit scoped connection factory required")
        self._connect_factory = connect_factory

    def recover(self, scope: TenantScope, *, attempt_id: str, insight_ref: AnalystExactRef,
                source_requests: list[AnalysisBundleSourceRequest], actor: str, markings: list[str],
                now: datetime, max_source_age: timedelta, max_bytes: int) -> AnalystExactRef:
        if (not actor.strip() or not attempt_id.strip() or insight_ref.resource_type != "InsightRevision"
                or now.utcoffset() is None or max_source_age <= timedelta(0)
                or type(max_bytes) is not int or max_bytes <= 0):
            raise ValueError("explicit diagnosis identity, clock and source limits required")
        identity = canonical_hash({"tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                                   "attemptId": attempt_id})
        key = "diagnosis-receive:" + identity
        with self._connect_factory(scope) as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))

            @contextmanager
            def bound(requested_scope):
                if requested_scope != scope:
                    raise ValueError("transaction scope mismatch")
                yield conn

            attempt = AipAgentRunExecutionService(bound).get(scope, attempt_id)
            if ((attempt.tenant.org_id, attempt.tenant.project_id) != scope.key
                    or attempt.attempt_id != attempt_id or attempt.created_by != actor
                    or attempt.status != "succeeded" or not attempt.completed_at
                    or attempt.completed_at.utcoffset() is None or not attempt.provider_receipt_id
                    or not attempt.usage_receipt_ids or attempt.reason_code is not None
                    or attempt.output_artifact_ref is None):
                raise ValueError("proven successful scoped diagnosis required")
            run = AipAgentRunService(bound).get(scope, attempt.agent_run_id)
            if ((run.tenant.org_id, run.tenant.project_id) != scope.key
                    or run.agent_run_id != attempt.agent_run_id
                    or run.request.skill.asset_type != "SkillTemplate"
                    or run.request.skill.asset_id != "ecommerce.skill.D02"
                    or run.request.model_route != attempt.route_ref or run.request.policy != attempt.policy_ref):
                raise ValueError("generation does not belong to the scoped D02 workflow")
            artifact = attempt.output_artifact_ref
            answer = read_agent_text(conn, scope, artifact, markings=markings)
            row = conn.execute(
                "SELECT run_id,source FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s",
                (*scope.key, artifact.artifact_id),
            ).fetchone()
            if (row is None or row["run_id"] != run.task_run_id or not isinstance(row["source"], dict)
                    or row["source"].get("agentRunId") != run.agent_run_id
                    or row["source"].get("attemptId") != attempt.attempt_id):
                raise ValueError("persisted diagnosis artifact provenance mismatch")
            expected_artifact = AnalystExactRef(resourceType="Artifact", resourceId=artifact.artifact_id,
                                                revision=1, contentHash=artifact.content_hash)
            owner = EcommerceAnalystAuthorityStore(bound)
            replay = owner.find_decision_publication_receipt(scope, key)
            if replay is not None:
                old = owner.get_decision_exact(scope, replay)
                if (old.created_by != actor or old.insight_ref != insight_ref
                        or old.generation_artifact_ref != expected_artifact
                        or old.decision_id != "diagnosis-" + identity[:40] or old.revision != 1):
                    raise ValueError("diagnosis replay command drifted")
                return replay
            insight = require_current_revision(conn, scope, insight_ref)
            if (insight.cutoff_at.utcoffset() is None or insight.cutoff_at > now
                    or now - insight.cutoff_at > max_source_age):
                raise ValueError("insight cutoff is stale or future")
            if not isinstance(source_requests, list) or not 1 <= len(source_requests) <= 100:
                raise ValueError("bounded complete source inventory required")
            requests = [AnalysisBundleSourceRequest.model_validate(item) for item in source_requests]
            def ref_key(ref):
                return ref.resource_type, ref.resource_id, ref.revision, ref.content_hash
            indexed = {ref_key(item.bundle_ref): item for item in requests}
            if (len(indexed) != len(requests)
                    or set(indexed) != {ref_key(ref) for ref in insight.evidence_refs}):
                raise ValueError("diagnosis source inventory mismatch")
            inputs = {(ref.resource_type, ref.resource_id, ref.revision, ref.authority)
                      for ref in run.request.input_refs}
            required = {(ref.resource_type, ref.resource_id, str(ref.revision), "postgresql")
                        for ref in [insight_ref, *insight.evidence_refs]}
            if not required.issubset(inputs):
                raise ValueError("D02 run did not declare exact diagnosis inputs")
            materials = []
            for ref in insight.evidence_refs:
                materials.append(read_analysis_bundle(conn=conn, scope=scope, task_id=run.task_id, actor=actor,
                    request=indexed[ref_key(ref)], markings=markings, now=now,
                    max_source_age=max_source_age, max_bytes=max_bytes))
                if len(json.dumps(materials, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                                  allow_nan=False, default=str).encode("utf-8")) > max_bytes:
                    raise ValueError("complete diagnosis material exceeds byte limit")
            decision = decision_from_completed_generation(insight=insight, materials=materials,
                                                         attempt=attempt, answer=answer, actor=actor)
            return owner.publish_decision(scope, actor, key, decision, expected_version=0)
