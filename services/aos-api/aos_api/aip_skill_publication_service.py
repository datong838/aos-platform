"""Governed Eval-to-published Skill revision service for BIND-3."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from aos_api.aip_agent_registry_contracts import (
    PublishEvaluatedSkillRevisionRequest,
    PublishSkillTemplateRequest,
    RegistryReceipt,
    SkillTemplateRevision,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryConflict,
    AipAgentRegistryNotFound,
    AipAgentRegistryPersistenceError,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityStore,
    AipEvalGateDependencyBlocked,
)
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    ModelRuntimeStoreError,
    evaluation_candidate_ref,
)
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.tenant_scope import TenantScope


class SkillPublicationRouteAuthority(Protocol):
    def require_ready(
        self,
        scope: TenantScope,
        route_ref: VersionedAssetRef,
        policy_ref: VersionedAssetRef,
        *,
        evaluated_at: datetime,
    ) -> None: ...


class SkillLogicPublicationAuthority(Protocol):
    def require_published(
        self,
        conn,
        scope: TenantScope,
        canonical_logic_id: str,
        logic_revision_ref: VersionedAssetRef,
    ) -> None: ...


class PostgresSkillLogicPublicationAuthority:
    def require_published(
        self,
        conn,
        scope: TenantScope,
        canonical_logic_id: str,
        logic_revision_ref: VersionedAssetRef,
    ) -> None:
        if canonical_logic_id != logic_revision_ref.asset_id:
            raise AipAgentRegistryTransitionBlocked(
                "skill canonical logic id does not match the exact LogicRevision"
            )
        row = conn.execute(
            """SELECT 1 FROM aip_logic_graph_revision r
               JOIN aip_logic_publication p
                 ON p.org_id=r.org_id AND p.project_id=r.project_id
                AND p.graph_id=r.graph_id AND p.graph_revision=r.revision
                AND p.graph_hash=r.graph_hash
               WHERE r.org_id=%s AND r.project_id=%s AND r.graph_id=%s
                 AND r.revision=%s AND r.graph_hash=%s LIMIT 1""",
            (
                *scope.key,
                logic_revision_ref.asset_id,
                logic_revision_ref.revision,
                logic_revision_ref.content_hash,
            ),
        ).fetchone()
        if row is None:
            raise AipAgentRegistryTransitionBlocked(
                "skill publication requires an exact published LogicRevision"
            )


class PostgresSkillPublicationRouteAuthority:
    def __init__(
        self,
        *,
        store: AipModelRuntimeStore | None = None,
        eval_authority: AipEvalAuthorityStore | None = None,
    ) -> None:
        self._store = store or AipModelRuntimeStore()
        self._eval_authority = eval_authority or AipEvalAuthorityStore()

    def require_ready(
        self,
        scope: TenantScope,
        route_ref: VersionedAssetRef,
        policy_ref: VersionedAssetRef,
        *,
        evaluated_at: datetime,
    ) -> None:
        try:
            route = self._store.get_route(scope, route_ref.asset_id, route_ref.revision)
            policy = self._store.get_policy(
                scope, policy_ref.asset_id, policy_ref.revision
            )
            self._eval_authority.require_exact_passed(
                scope,
                route.eval_gate_ref,
                expected_target=evaluation_candidate_ref(route),
                now=evaluated_at,
            )
        except (ModelRuntimeStoreError, AipEvalGateDependencyBlocked) as exc:
            raise AipAgentRegistryTransitionBlocked(
                "skill publication model route is unavailable"
            ) from exc
        if (
            route.content_hash != route_ref.content_hash
            or route.lifecycle is not ModelRuntimeLifecycle.ACTIVE
            or route.runtime_policy_ref != policy_ref
            or policy.content_hash != policy_ref.content_hash
            or policy.lifecycle is not ModelRuntimeLifecycle.ACTIVE
            or policy.kill_switch_enabled
        ):
            raise AipAgentRegistryTransitionBlocked(
                "skill publication requires exact active route, policy, and Eval gate"
            )


class AipSkillPublicationService(AipSkillRegistry):
    """Create a new immutable published revision without mutating evaluated r1."""

    _OPERATION = "skill_template.publish_evaluated"

    def __init__(
        self,
        connect_factory=None,
        *,
        route_authority=None,
        logic_authority=None,
    ) -> None:
        super().__init__(connect_factory)
        self._route_authority = (
            route_authority or PostgresSkillPublicationRouteAuthority()
        )
        self._logic_authority = (
            logic_authority or PostgresSkillLogicPublicationAuthority()
        )

    def publish_evaluated_revision(
        self,
        scope: TenantScope,
        request: PublishEvaluatedSkillRevisionRequest,
        *,
        actor: str,
        occurred_at: datetime | None = None,
    ) -> tuple[SkillTemplateRevision, RegistryReceipt]:
        self._validate_command(scope, request.idempotency_key, actor)
        happened_at = occurred_at or datetime.now(UTC)
        request_hash = self._command_hash(request, actor)
        try:
            with self._connect_factory(scope) as conn:
                self._lock(conn, scope, self._OPERATION, request.idempotency_key)
                replay = self._receipt_row(
                    conn, scope, self._OPERATION, request.idempotency_key
                )
                if replay is not None:
                    self._require_replay_hash(replay, request_hash)
                    skill_id, revision = self._parse_result_id(
                        replay["result_ref"]["resourceId"]
                    )
                    row = self._skill_row(conn, skill_id, revision)
                    if row is None:
                        raise AipAgentRegistryNotFound(
                            "published skill revision referenced by receipt is missing"
                        )
                    return self._skill_from_row(row), self._receipt_from_row(
                        scope, replay
                    )

                source_row = self._skill_row(
                    conn,
                    request.source_skill.asset_id,
                    request.source_skill.revision,
                )
                if source_row is None:
                    raise AipAgentRegistryNotFound(
                        "evaluated source skill revision not found"
                    )
                source = self._skill_from_row(source_row)
                if (
                    source.lifecycle is not TemplateLifecycle.EVALUATED
                    or source.content_hash != request.source_skill.content_hash
                ):
                    raise AipAgentRegistryTransitionBlocked(
                        "skill publication requires an exact evaluated source revision"
                    )

                gate_row = conn.execute(
                    """SELECT status,decision_hash,target_ref
                       FROM aip_release_gate_decision
                       WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                    (*scope.key, request.release_gate_decision_id),
                ).fetchone()
                if gate_row is None:
                    raise AipAgentRegistryNotFound(
                        "skill release gate decision not found"
                    )
                expected_target = AssetRevisionRef(
                    asset_type=AssetType.SKILL_TEMPLATE,
                    asset_id=source.skill_id,
                    revision=str(source.revision),
                    content_hash=source.content_hash,
                )
                if (
                    gate_row["status"] != "passed"
                    or AssetRevisionRef.model_validate(gate_row["target_ref"])
                    != expected_target
                ):
                    raise AipAgentRegistryTransitionBlocked(
                        "skill release gate is not passed for the exact source revision"
                    )

                event_row = conn.execute(
                    """SELECT event_id,event_type,release_gate_decision_id,target_ref
                       FROM aip_publication_event
                       WHERE org_id=%s AND project_id=%s AND publication_id=%s
                       ORDER BY occurred_at DESC,event_id DESC LIMIT 1""",
                    (*scope.key, request.publication_id),
                ).fetchone()
                if event_row is None:
                    raise AipAgentRegistryNotFound(
                        "skill publication event not found"
                    )
                if (
                    event_row["event_type"] != "published"
                    or event_row["release_gate_decision_id"]
                    != request.release_gate_decision_id
                    or AssetRevisionRef.model_validate(event_row["target_ref"])
                    != expected_target
                ):
                    raise AipAgentRegistryTransitionBlocked(
                        "skill publication event is revoked, drifted, or targets another revision"
                    )

                self._logic_authority.require_published(
                    conn,
                    scope,
                    source.canonical_logic_id,
                    request.logic_revision_ref,
                )

                self._route_authority.require_ready(
                    scope,
                    request.model_route_ref,
                    request.runtime_policy_ref,
                    evaluated_at=happened_at,
                )
                conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"aip6:skill-family:{source.skill_id}",),
                )
                latest = conn.execute(
                    """SELECT COALESCE(MAX(revision),0) AS revision
                       FROM aip_skill_template_revision WHERE skill_id=%s""",
                    (source.skill_id,),
                ).fetchone()
                revision = int(latest["revision"]) + 1
                gate_ref = VersionedAssetRef(
                    asset_type="EvalGateDecision",
                    asset_id=request.release_gate_decision_id,
                    revision=1,
                    content_hash=gate_row["decision_hash"],
                )
                publication_ref = ResourceRef(
                    resource_type="PublicationEvent",
                    resource_id=event_row["event_id"],
                    revision=request.publication_id,
                    authority="postgresql",
                )
                payload = source.model_dump(
                    mode="json",
                    by_alias=True,
                    exclude={"content_hash", "created_by", "created_at"},
                )
                payload.update(
                    revision=revision,
                    lifecycle=TemplateLifecycle.PUBLISHED.value,
                    parentRef=request.source_skill.model_dump(
                        mode="json", by_alias=True
                    ),
                    publicationTenant=TenantContext(
                        org_id=scope.org_id, project_id=scope.project_id
                    ).model_dump(mode="json", by_alias=True),
                    releaseGateRef=gate_ref.model_dump(mode="json", by_alias=True),
                    publicationRef=publication_ref.model_dump(
                        mode="json", by_alias=True
                    ),
                    modelRouteRef=request.model_route_ref.model_dump(
                        mode="json", by_alias=True
                    ),
                    runtimePolicyRef=request.runtime_policy_ref.model_dump(
                        mode="json", by_alias=True
                    ),
                    logicRevisionRef=request.logic_revision_ref.model_dump(
                        mode="json", by_alias=True
                    ),
                )
                published_request = PublishSkillTemplateRequest(
                    **payload, content_hash=self._hash(payload)
                )
                row = conn.execute(
                    """INSERT INTO aip_skill_template_revision
                       (skill_id,revision,canonical_logic_id,lifecycle,input_schema,
                        output_schema,tool_allowlist,required_capabilities,risk_level,
                        eval_pack_ref,memory_policy_ref,handoff_policy_ref,source_ref,
                        source_license,parent_ref,publication_tenant,release_gate_ref,
                        publication_ref,model_route_ref,runtime_policy_ref,logic_revision_ref,content_hash,
                        created_by,created_at)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                        %s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s)
                       RETURNING *""",
                    (
                        published_request.skill_id,
                        published_request.revision,
                        published_request.canonical_logic_id,
                        published_request.lifecycle.value,
                        self._json(published_request.input_schema),
                        self._json(published_request.output_schema),
                        self._json(published_request.tool_allowlist),
                        self._json(published_request.required_capabilities),
                        published_request.risk_level,
                        self._json(published_request.eval_pack_ref)
                        if published_request.eval_pack_ref
                        else None,
                        self._json(published_request.memory_policy_ref),
                        self._json(published_request.handoff_policy_ref),
                        self._json(published_request.source_ref),
                        published_request.source_license,
                        self._json(published_request.parent_ref),
                        self._json(published_request.publication_tenant),
                        self._json(published_request.release_gate_ref),
                        self._json(published_request.publication_ref),
                        self._json(published_request.model_route_ref),
                        self._json(published_request.runtime_policy_ref),
                        self._json(published_request.logic_revision_ref),
                        published_request.content_hash,
                        actor.strip(),
                        happened_at,
                    ),
                ).fetchone()
                receipt = self._insert_receipt(
                    conn,
                    scope,
                    self._OPERATION,
                    request.idempotency_key,
                    request_hash,
                    "PublicationEvent",
                    request.publication_id,
                    "SkillTemplate",
                    self._result_id(source.skill_id, revision),
                    actor,
                    happened_at,
                )
                conn.commit()
                return self._skill_from_row(row), receipt
        except (
            AipAgentRegistryConflict,
            AipAgentRegistryNotFound,
            AipAgentRegistryTransitionBlocked,
        ):
            raise
        except Exception as exc:
            raise AipAgentRegistryPersistenceError(
                "governed skill publication failed"
            ) from exc

    @staticmethod
    def _result_id(skill_id: str, revision: int) -> str:
        return f"{skill_id}@r{revision}"

    @staticmethod
    def _parse_result_id(value: str) -> tuple[str, int]:
        skill_id, separator, revision = value.rpartition("@r")
        if not separator or not skill_id:
            raise AipAgentRegistryNotFound(
                "published skill receipt result is invalid"
            )
        try:
            return skill_id, int(revision)
        except ValueError as exc:
            raise AipAgentRegistryNotFound(
                "published skill receipt result is invalid"
            ) from exc
