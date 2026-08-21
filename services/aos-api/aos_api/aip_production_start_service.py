"""W2-D production start composition gate and append-only decision authority."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from aos_api.aip_action_store import AipActionStore
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
    ProductionContractNotFound,
    canonical_hash,
    compute_action_binding_hash,
)
from aos_api.aip_production_contracts import (
    ContractBlocker,
    ProductionStartDecision,
    ProductionStartDecisionListResponse,
    ProductionStartDecisionStatus,
    ProductionStartRequest,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


class AipProductionStartService:
    def __init__(
        self,
        *,
        contract_store: AipProductionContractStore | None = None,
        action_store: AipActionStore | None = None,
        task_store: AipTaskStore | None = None,
    ) -> None:
        self._contracts = contract_store or AipProductionContractStore()
        self._actions = action_store or AipActionStore()
        self._tasks = task_store or AipTaskStore()

    def start(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        body: ProductionStartRequest,
    ) -> ProductionStartDecision:
        request_hash = canonical_hash(body.model_dump(mode="json", by_alias=True))
        decision_id = f"start-decision-{uuid.uuid4().hex[:20]}"
        with connect(scope) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"aip-w2d-start:{scope.org_id}:{scope.project_id}:{idempotency_key}",),
            )
            replay = conn.execute(
                """SELECT * FROM aip_production_start_decision
                   WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
                (*scope.key, idempotency_key),
            ).fetchone()
            if replay is not None:
                if replay["request_hash"] != request_hash:
                    raise ProductionContractIdempotencyConflict(
                        "idempotency key payload drift"
                    )
                return self._decision(scope, replay)
            task = conn.execute(
                """SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s
                   AND task_id=%s FOR UPDATE""",
                (*scope.key, body.task_id),
            ).fetchone()
            if task is None:
                raise ProductionContractNotFound("task not found in scope")
            snapshot: list[dict[str, Any]] = []
            blockers: list[ContractBlocker] = []
            plan = self._check_plan(conn, scope, body, task, snapshot, blockers)
            preview = self._check_preview(conn, scope, body, snapshot, blockers)
            self._check_production_context(conn, scope, body, preview, snapshot, blockers)
            self._check_action(conn, scope, body, preview, snapshot, blockers)
            self._check_logic(conn, scope, body, snapshot, blockers)
            status = self._blocked_status(blockers)
            task_run_ref: dict[str, Any] | None = None
            if not blockers and plan is not None:
                run = self._tasks.create_run_from_production_start_gate(
                    conn,
                    scope,
                    actor=actor,
                    decision_id=decision_id,
                    task_id=body.task_id,
                    expected_task_version=body.expected_task_version,
                    plan_revision_id=body.plan_ref.resource_id,
                    plan_content_hash=body.plan_ref.content_hash,
                    logic_graph_id=body.logic_graph_id,
                    logic_revision=body.logic_revision,
                )
                status = ProductionStartDecisionStatus.STARTED
                task_run_ref = {
                    "resourceType": "TaskRun",
                    "resourceId": run.id,
                    "revision": str(run.version),
                    "authority": "aip-task-runtime",
                }
            blocker_payload = [
                item.model_dump(mode="json", by_alias=True) for item in blockers
            ]
            row = conn.execute(
                """INSERT INTO aip_production_start_decision
                   (org_id,project_id,decision_id,status,task_id,plan_ref,preview_ref,
                    action_proposal_ref,dependency_snapshot_hash,blockers,task_run_ref,
                    idempotency_key,request_hash,created_by)
                   VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,
                          %s::jsonb,%s,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    decision_id,
                    status.value,
                    body.task_id,
                    self._json(body.plan_ref.model_dump(mode="json", by_alias=True)),
                    self._json(body.preview_ref.model_dump(mode="json", by_alias=True)),
                    self._json(
                        body.action_proposal_ref.model_dump(mode="json", by_alias=True)
                    ),
                    canonical_hash(snapshot),
                    self._json(blocker_payload),
                    None if task_run_ref is None else self._json(task_run_ref),
                    idempotency_key,
                    request_hash,
                    actor,
                ),
            ).fetchone()
            conn.commit()
            return self._decision(scope, row)

    def get(
        self, scope: TenantScope, decision_id: str
    ) -> ProductionStartDecision:
        with connect(scope) as conn:
            row = conn.execute(
                """SELECT * FROM aip_production_start_decision
                   WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone()
        if row is None:
            raise ProductionContractNotFound("production start decision not found")
        return self._decision(scope, row)

    def list(self, scope: TenantScope) -> ProductionStartDecisionListResponse:
        with connect(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_production_start_decision
                   WHERE org_id=%s AND project_id=%s
                   ORDER BY created_at DESC,decision_id""",
                scope.key,
            ).fetchall()
        items = [self._decision(scope, row) for row in rows]
        return ProductionStartDecisionListResponse(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            items=items,
            count=len(items),
        )

    def _check_plan(
        self,
        conn: Any,
        scope: TenantScope,
        body: ProductionStartRequest,
        task: Any,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
    ) -> Any | None:
        plan = conn.execute(
            """SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s
               AND plan_revision_id=%s FOR UPDATE""",
            (*scope.key, body.plan_ref.resource_id),
        ).fetchone()
        observed = {
            "resourceType": "Task",
            "resourceId": body.task_id,
            "expectedVersion": body.expected_task_version,
            "observedVersion": int(task["version"]),
            "status": task["status"],
            "currentPlanRevisionId": task["current_plan_revision_id"],
        }
        snapshot.append(observed)
        if int(task["version"]) != body.expected_task_version:
            blockers.append(ContractBlocker(code="TASK_VERSION_DRIFTED", message="Task version 漂移"))
        if task["status"] not in {"planning", "awaiting_approval"}:
            blockers.append(
                ContractBlocker(
                    code="TASK_NOT_AWAITING_START",
                    message="Task 不处于生产启动候选状态",
                )
            )
        if plan is None or plan["task_id"] != body.task_id:
            raise ProductionContractNotFound(
                "plan revision not found for task in scope"
            )
        production_contract = dict(plan["risk"] or {}).get("productionContract")
        snapshot.append(
            {
                "resourceType": "PlanRevision",
                "resourceId": plan["plan_revision_id"],
                "expectedRevision": body.plan_ref.revision,
                "observedRevision": int(plan["revision"]),
                "expectedHash": body.plan_ref.content_hash,
                "observedHash": plan["content_hash"],
                "approvalStatus": plan["approval_status"],
                "productionContract": production_contract,
            }
        )
        if task["current_plan_revision_id"] != plan["plan_revision_id"]:
            blockers.append(ContractBlocker(code="PLAN_NOT_CURRENT", message="PlanRevision 不是 Task 当前计划", resource_ref=body.plan_ref))
        if int(plan["revision"]) != body.plan_ref.revision or plan["content_hash"] != body.plan_ref.content_hash:
            blockers.append(ContractBlocker(code="PLAN_EXACT_REF_DRIFTED", message="PlanRevision exact ref 漂移", resource_ref=body.plan_ref))
        if plan["approval_status"] != "draft":
            blockers.append(ContractBlocker(code="PLAN_NOT_AWAITING_START", message="PlanRevision 不处于待组合门批准状态", resource_ref=body.plan_ref))
        if not isinstance(production_contract, dict) or not (
            production_contract.get("compilerVersion") == "w2c.v1"
            and production_contract.get("productionStartGateRequired") is True
            and production_contract.get("productionStartGateRef") is None
        ):
            blockers.append(ContractBlocker(code="PLAN_NOT_W2C_PRODUCTION_DRAFT", message="PlanRevision 不是受 W2-D 保护的 W2-C 生产草案", resource_ref=body.plan_ref))
        return plan

    def _check_preview(
        self,
        conn: Any,
        scope: TenantScope,
        body: ProductionStartRequest,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
    ) -> Any | None:
        row = conn.execute(
            """SELECT * FROM aip_impact_preview_revision
               WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=%s""",
            (*scope.key, body.preview_ref.resource_id, body.preview_ref.revision),
        ).fetchone()
        if row is None:
            raise ProductionContractNotFound("impact preview not found in scope")
        # Lock every mutable authority before re-validating the frozen snapshot.
        # This closes the check/use window between dependency validation and start.
        self._lock_mutable_bindings(conn, scope, row["binding_refs"])
        try:
            row = self._contracts.assert_frozen_preview_current(
                conn, scope, body.preview_ref
            )
        except ProductionContractDependencyBlocked as exc:
            raw_code = str(exc).split(":", 1)[0]
            blockers.append(
                ContractBlocker(
                    code=raw_code
                    if raw_code.startswith("IMPACT_PREVIEW_")
                    else "IMPACT_PREVIEW_DEPENDENCY_BLOCKED",
                    message="ImpactPreview 未通过 exact 当前性门",
                    resource_ref=body.preview_ref,
                )
            )
            return None
        snapshot.append(
            {
                "resourceType": "ImpactPreviewRevision",
                "resourceId": row["preview_id"],
                "revision": int(row["revision"]),
                "contentHash": row["content_hash"],
                "dependencySnapshotHash": row["dependency_snapshot_hash"],
            }
        )
        plan_ref = row["plan_ref"]
        if isinstance(plan_ref, str):
            plan_ref = json.loads(plan_ref)
        if row["task_id"] != body.task_id or not (
            plan_ref.get("resourceId") == body.plan_ref.resource_id
            and int(plan_ref.get("revision", 0)) == body.plan_ref.revision
            and plan_ref.get("contentHash") == body.plan_ref.content_hash
        ):
            blockers.append(ContractBlocker(code="PREVIEW_TASK_PLAN_MISMATCH", message="ImpactPreview 未绑定本次 Task/Plan exact ref", resource_ref=body.preview_ref))
        return row

    def _check_production_context(
        self,
        conn: Any,
        scope: TenantScope,
        body: ProductionStartRequest,
        preview: Any | None,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
    ) -> None:
        ref = body.production_context_ref
        row = conn.execute(
            """SELECT * FROM aip_production_context_revision
               WHERE org_id=%s AND project_id=%s AND context_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        snapshot.append(
            {
                "resourceType": ref.resource_type,
                "resourceId": ref.resource_id,
                "expectedRevision": ref.revision,
                "expectedHash": ref.content_hash,
                "observedHash": None if row is None else row["content_hash"],
                "lifecycle": None if row is None else row["lifecycle"],
                "readiness": None if row is None else row["readiness"],
            }
        )
        if row is None or row["content_hash"] != ref.content_hash:
            blockers.append(
                ContractBlocker(
                    code="PRODUCTION_CONTEXT_EXACT_REF_MISSING_OR_DRIFTED",
                    message="ProductionContext exact ref 不可用",
                    resource_ref=ref,
                )
            )
            return
        if row["lifecycle"] != "frozen" or row["readiness"] != "ready":
            blockers.append(
                ContractBlocker(
                    code="PRODUCTION_CONTEXT_NOT_READY",
                    message="ProductionContext 未 frozen/ready",
                    resource_ref=ref,
                )
            )
        if preview is None:
            return
        pairs = (
            ("brief_ref", "brief_ref"),
            ("evidence_bundle_ref", "evidence_bundle_ref"),
            ("eval_contract_ref", "eval_contract_ref"),
            ("responsibility_plan_ref", "responsibility_plan_ref"),
        )
        for context_col, preview_col in pairs:
            left = self._contracts._load(row[context_col])
            right = self._contracts._load(preview[preview_col])
            if left != right:
                blockers.append(
                    ContractBlocker(
                        code="PRODUCTION_CONTEXT_PREVIEW_CONTRACT_MISMATCH",
                        message=f"ProductionContext 与 Preview 的 {preview_col} 不一致",
                        resource_ref=ref,
                    )
                )
                break
        if row["task_id"] != body.task_id:
            blockers.append(
                ContractBlocker(
                    code="PRODUCTION_CONTEXT_TASK_MISMATCH",
                    message="ProductionContext taskId 与 Start 请求不一致",
                    resource_ref=ref,
                )
            )

    def _check_action(
        self,
        conn: Any,
        scope: TenantScope,
        body: ProductionStartRequest,
        preview: Any | None,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
    ) -> None:
        ref = body.action_proposal_ref
        row = conn.execute(
            """SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s
               AND proposal_id=%s FOR UPDATE""",
            (*scope.key, ref.proposal_id),
        ).fetchone()
        if row is None:
            raise ProductionContractNotFound("action proposal not found in scope")
        snapshot.append(
            {
                "resourceType": "ActionProposal",
                "resourceId": row["proposal_id"],
                "expectedVersion": ref.version,
                "observedVersion": int(row["version"]),
                "expectedHash": ref.proposal_hash,
                "observedHash": row["proposal_hash"],
                "status": row["status"],
            }
        )
        if int(row["version"]) != ref.version or row["proposal_hash"] != ref.proposal_hash:
            blockers.append(ContractBlocker(code="ACTION_PROPOSAL_DRIFTED", message="ActionProposal exact ref 漂移"))
        if row["status"] != "approved":
            blockers.append(ContractBlocker(code="ACTION_PROPOSAL_NOT_APPROVED", message="ActionProposal 尚未批准"))
        if row["expires_at"] <= datetime.now(timezone.utc):
            blockers.append(ContractBlocker(code="ACTION_PROPOSAL_EXPIRED", message="ActionProposal 已过期"))
        if row["task_id"] != body.task_id:
            blockers.append(ContractBlocker(code="ACTION_PROPOSAL_TASK_MISMATCH", message="ActionProposal 未绑定本次 Task"))
        if preview is None or not (
            row["impact_preview_id"] == body.preview_ref.resource_id
            and int(row["impact_preview_revision"] or 0) == body.preview_ref.revision
            and row["impact_preview_hash"] == body.preview_ref.content_hash
        ):
            blockers.append(ContractBlocker(code="ACTION_PREVIEW_BINDING_MISMATCH", message="ActionProposal 未绑定本次 ImpactPreview exact ref"))
        elif row["impact_preview_id"] is not None and preview is not None:
            draft = conn.execute(
                """SELECT snapshot FROM aip_action_draft
                   WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                   ORDER BY proposal_version DESC LIMIT 1""",
                (*scope.key, row["proposal_id"]),
            ).fetchone()
            draft_snapshot = draft["snapshot"] if draft is not None else None
            if isinstance(draft_snapshot, str):
                draft_snapshot = json.loads(draft_snapshot)
            pinned = (draft_snapshot or {}).get("actionBindingHash") if isinstance(draft_snapshot, dict) else None
            if not isinstance(pinned, str) or len(pinned) != 64:
                blockers.append(
                    ContractBlocker(
                        code="ACTION_BINDING_HASH_REQUIRED",
                        message="绑 Preview 的 ActionProposal 缺少 actionBindingHash",
                    )
                )
            else:
                binding_refs = preview["binding_refs"]
                capability_ref = preview["capability_ref"]
                account_ref = preview["account_ref"]
                if isinstance(binding_refs, str):
                    binding_refs = json.loads(binding_refs)
                if isinstance(capability_ref, str):
                    capability_ref = json.loads(capability_ref)
                if isinstance(account_ref, str):
                    account_ref = json.loads(account_ref)
                expected = compute_action_binding_hash(
                    org_id=scope.org_id,
                    project_id=scope.project_id,
                    preview_id=preview["preview_id"],
                    revision=int(preview["revision"]),
                    content_hash=preview["content_hash"],
                    dependency_snapshot_hash=preview["dependency_snapshot_hash"],
                    binding_refs=binding_refs,
                    capability_ref=capability_ref,
                    account_ref=account_ref,
                    expires_at=preview["expires_at"],
                )
                snapshot.append(
                    {
                        "resourceType": "ActionBindingHash",
                        "pinned": pinned,
                        "expected": expected,
                    }
                )
                if pinned != expected:
                    blockers.append(
                        ContractBlocker(
                            code="ACTION_BINDING_HASH_MISMATCH",
                            message="ActionProposal actionBindingHash 与 ImpactPreview 不一致",
                        )
                    )
        approvals = conn.execute(
            """SELECT actor_id,expires_at FROM aip_action_approval_event
               WHERE org_id=%s AND project_id=%s AND proposal_id=%s
                 AND decision='approved' FOR SHARE""",
            (*scope.key, row["proposal_id"]),
        ).fetchall()
        now = datetime.now(timezone.utc)
        valid = [item for item in approvals if item["expires_at"] is None or item["expires_at"] > now]
        minimum = int((row["policy_snapshot"] or {}).get("minimumApprovals", 1))
        if len(valid) < minimum:
            blockers.append(ContractBlocker(code="ACTION_APPROVAL_QUORUM_LOST", message="ActionProposal 有效审批数不足"))
        if not bool((row["policy_snapshot"] or {}).get("executionAllowed", True)):
            blockers.append(ContractBlocker(code="ACTION_EXECUTION_POLICY_BLOCKED", message="Action policy 禁止生产执行"))

    def _check_logic(
        self,
        conn: Any,
        scope: TenantScope,
        body: ProductionStartRequest,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
    ) -> None:
        graph = conn.execute(
            """SELECT status FROM aip_logic_graph
               WHERE org_id=%s AND project_id=%s AND graph_id=%s
                 AND deleted_at IS NULL FOR SHARE""",
            (*scope.key, body.logic_graph_id),
        ).fetchone()
        revision = conn.execute(
            """SELECT graph_hash, snapshot FROM aip_logic_graph_revision
               WHERE org_id=%s AND project_id=%s AND graph_id=%s AND revision=%s
               FOR SHARE""",
            (*scope.key, body.logic_graph_id, body.logic_revision),
        ).fetchone()
        snapshot.append(
            {
                "resourceType": "LogicGraphRevision",
                "resourceId": body.logic_graph_id,
                "revision": body.logic_revision,
                "status": graph["status"] if graph else None,
                "graphHash": revision["graph_hash"] if revision else None,
            }
        )
        if graph is None or revision is None:
            raise ProductionContractNotFound("logic graph revision not found in scope")
        if revision["graph_hash"] != body.logic_graph_hash:
            blockers.append(
                ContractBlocker(
                    code="LOGIC_GRAPH_HASH_MISMATCH",
                    message="LogicGraph revision/hash 与权威不一致",
                )
            )
        if graph["status"] != "published":
            blockers.append(ContractBlocker(code="LOGIC_GRAPH_NOT_PUBLISHED", message="LogicGraph 尚未发布"))
        payload = revision["snapshot"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        nodes = (payload or {}).get("nodes") if isinstance(payload, dict) else None
        if not isinstance(nodes, list) or len(nodes) == 0:
            blockers.append(
                ContractBlocker(
                    code="LOGIC_GRAPH_EMPTY",
                    message="空 LogicGraph 不可进入 ProductionStart",
                )
            )

    @staticmethod
    def _lock_mutable_bindings(
        conn: Any, scope: TenantScope, value: Any
    ) -> None:
        refs = json.loads(value) if isinstance(value, str) else value
        mapping = {
            "AgentInstance": ("aip_agent_instance", "instance_id"),
            "SkillBinding": ("aip_skill_binding", "binding_id"),
            "CapabilityBinding": ("aip_capability_binding", "binding_id"),
        }
        for ref in refs or []:
            table, column = mapping[ref["resourceType"]]
            conn.execute(
                f"SELECT 1 FROM {table} WHERE org_id=%s AND project_id=%s AND {column}=%s FOR UPDATE",
                (*scope.key, ref["resourceId"]),
            ).fetchone()

    @staticmethod
    def _blocked_status(
        blockers: list[ContractBlocker],
    ) -> ProductionStartDecisionStatus:
        codes = [item.code for item in blockers]
        if any("UNKNOWN" in code for code in codes):
            return ProductionStartDecisionStatus.UNKNOWN
        if any("DRIFTED" in code or "EXPIRED" in code or "NOT_CURRENT" in code for code in codes):
            return ProductionStartDecisionStatus.STALE
        return ProductionStartDecisionStatus.BLOCKED

    @staticmethod
    def _decision(scope: TenantScope, row: Any) -> ProductionStartDecision:
        def load(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        return ProductionStartDecision(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            decision_id=row["decision_id"],
            status=row["status"],
            task_id=row["task_id"],
            plan_ref=load(row["plan_ref"]),
            preview_ref=load(row["preview_ref"]),
            action_proposal_ref=load(row["action_proposal_ref"]),
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            blockers=load(row["blockers"]),
            task_run_ref=load(row["task_run_ref"]),
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
