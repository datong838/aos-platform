"""Internal D01 recovery: retained original answer to a scoped portrait.

No Provider call or public route. Identity, markings and source grants must be
supplied by the authorized server workflow. Replays read historical results;
they do not renew authority for subsequent generation or execution.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_text_output import read_agent_text
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_portrait_generation import insight_from_completed_generation
from aos_api.ecommerce_analyst_portrait_inputs import read_portrait_inputs
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope


class PortraitReceiver:
    def __init__(self, connect_factory):
        if not callable(connect_factory):
            raise ValueError("explicit scoped connection factory required")
        self._connect_factory = connect_factory

    def recover_with_formal_source(
            self, scope: TenantScope, *, source_service, parent_request, source_ref,
            installation_id, installation_revision, installation_etag, **recovery):
        """Publish original retained output while original Source locks remain held."""
        from aos_api.aip_formal_source_disclosure import FormalSourceDisclosureService
        if type(source_service) is not FormalSourceDisclosureService:
            raise TypeError('original formal Source service required')
        with source_service.source_transaction(
                scope, recovery.get('actor'), parent_request, source_ref=source_ref,
                installation_id=installation_id,
                installation_revision=installation_revision,
                installation_etag=installation_etag) as (conn, store):
            @contextmanager
            def bound(requested_scope):
                if requested_scope != scope:
                    raise ValueError('portrait formal Source transaction scope mismatch')
                yield conn
            return PortraitReceiver(bound).recover(scope, source_store=store, **recovery)

    def recover(self, scope: TenantScope, *, attempt_id: str, method_ref: AnalystExactRef, eval_ref: AnalystExactRef, cutoff_at: datetime,
                metric_sources: list, actor: str, markings: list[str],
                now: datetime, max_source_age: timedelta, max_bytes: int, source_store=None) -> AnalystExactRef:
        if (any(type(value) is not str or not value or value.strip()!=value or len(value)>200 for value in (actor,attempt_id))
                or method_ref.resource_type != "MethodRevision" or eval_ref.resource_type != "EvalContractRevision"
                or any(not isinstance(value,datetime) or value.utcoffset() is None for value in (now,cutoff_at))
                or not isinstance(max_source_age,timedelta) or max_source_age <= timedelta(0)
                or type(max_bytes) is not int or not 1 <= max_bytes <= 2_000_000):
            raise ValueError("explicit portrait identity, clock and source limits required")
        identity = canonical_hash({"tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                                   "attemptId": attempt_id})
        key = "portrait-receive:" + identity
        with self._connect_factory(scope) as conn:
            if source_store is not None:
                from aos_api.aip_metric_query_evidence import _production
                _production(conn, scope, source_store)
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
                    or attempt.completed_at.utcoffset() is None or attempt.completed_at > now or not attempt.provider_receipt_id
                    or not attempt.usage_receipt_ids or attempt.reason_code is not None
                    or attempt.output_artifact_ref is None):
                raise ValueError("proven successful scoped portrait required")
            run = AipAgentRunService(bound).get(scope, attempt.agent_run_id)
            if ((run.tenant.org_id, run.tenant.project_id) != scope.key
                    or run.agent_run_id != attempt.agent_run_id
                    or run.request.skill.asset_type != "SkillTemplate"
                    or run.request.skill.asset_id != "ecommerce.skill.D01"
                    or run.request.model_route != attempt.route_ref or run.request.policy != attempt.policy_ref):
                raise ValueError("generation does not belong to the scoped D01 workflow")
            artifact = attempt.output_artifact_ref
            answer = read_agent_text(conn, scope, artifact, markings=markings)
            row = conn.execute(
                "SELECT run_id,source FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s",
                (*scope.key, artifact.artifact_id),
            ).fetchone()
            if (row is None or row["run_id"] != run.task_run_id or not isinstance(row["source"], dict)
                    or row["source"].get("agentRunId") != run.agent_run_id
                    or row["source"].get("attemptId") != attempt.attempt_id):
                raise ValueError("persisted portrait artifact provenance mismatch")
            expected_artifact = AnalystExactRef(resourceType="Artifact", resourceId=artifact.artifact_id,
                                                revision=1, contentHash=artifact.content_hash)
            owner = EcommerceAnalystAuthorityStore(TransactionBoundConnectFactory(HostTransaction(conn), scope))
            replay = owner.find_insight_publication_receipt(scope, key)
            if replay is not None:
                old = owner.get_insight_exact(scope, replay)
                if (old.created_by != actor or old.method_ref != method_ref or old.eval_ref != eval_ref or old.cutoff_at != cutoff_at
                        or old.generation_artifact_ref != expected_artifact
                        or old.insight_id != "portrait-" + identity[:40] or old.revision != 1):
                    raise ValueError("portrait replay command drifted")
                return replay
            inputs = read_portrait_inputs(conn=conn, scope=scope, run=run, actor=actor,
                method_ref=method_ref, eval_ref=eval_ref, metric_sources=metric_sources, cutoff_at=cutoff_at,
                markings=markings, now=now, max_source_age=max_source_age, max_bytes=max_bytes,
                **({'source_store': source_store} if source_store is not None else {}))
            insight = insight_from_completed_generation(attempt=attempt, answer=answer, actor=actor, **inputs)
            ref = owner.publish_insight(scope, actor, key, insight, expected_version=0)
            if source_store is not None:
                # The transaction-bound Owner cannot commit. Validate the live
                # Source before this native commit; unknown outcomes propagate.
                source_store._formal_source_authority.validate_commit(conn, scope)
                conn.commit()
            return ref
