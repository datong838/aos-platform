"""Tenant-scoped readonly discovery of live EvalRun options for one exact Route."""

from __future__ import annotations

from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType, EvalRunStatus
from aos_api.aip_model_route_eval_context_reader import _boundary, _json_text, _same_original_json
from aos_api.aip_model_route_eval_subject_binding import _fresh
from aos_api.aip_model_runtime_contracts import ModelEvalCandidate
from aos_api.tenant_scope import TenantScope


def list_route_eval_run_options(
    conn,
    *,
    expected_database: str,
    scope: TenantScope,
    candidate: ModelEvalCandidate,
    limit: int = 20,
):
    """Return only exact live contracted Run records from the caller snapshot."""
    if (
        type(scope) is not TenantScope
        or type(expected_database) is not str
        or not expected_database
        or expected_database != expected_database.strip()
        or type(candidate) is not ModelEvalCandidate
        or type(limit) is not int
        or not 1 <= limit <= 20
    ):
        raise ValueError("exact route candidate, tenant, database and limit required")
    claim = _fresh(candidate, ModelEvalCandidate)
    if (
        claim.source_ref.asset_type != "ModelRouteRevision"
        or claim.target_ref.asset_type != "ModelRouteRevision"
        or claim.source_lifecycle != "draft"
        or type(claim.execution_allowed) is not bool
        or claim.execution_allowed
    ):
        raise ValueError("nonexecuting draft Route candidate required")

    evaluated_at = _boundary(conn, expected_database, scope)
    target = AssetRevisionRef(
        assetType=AssetType.MODEL_ROUTE,
        assetId=claim.target_ref.asset_id,
        revision=str(claim.target_ref.revision),
        contentHash=claim.target_ref.content_hash,
    )
    rows = conn.execute(
        """SELECT * FROM aip_eval_run
           WHERE org_id=%s AND project_id=%s
             AND status IN ('queued','running')
             AND eval_contract_ref IS NOT NULL
             AND target_ref=%s::jsonb
           ORDER BY created_at DESC,run_id ASC LIMIT %s""",
        (*scope.key, _json_text(target.model_dump(mode="json", by_alias=True)), limit),
    ).fetchall()
    if type(rows) is not list or len(rows) > limit:
        raise ValueError("bounded original Run rows required")

    authority = AipEvalAuthorityStore()
    options = []
    for row in rows:
        if type(row) is not dict:
            raise ValueError("original Run row must retain named columns")
        run = authority._run_from_row(row)
        _same_original_json(
            row.get("target_ref"), run.target.model_dump(mode="json", by_alias=True)
        )
        _same_original_json(
            row.get("eval_contract_ref"),
            run.eval_contract_ref.model_dump(mode="json", by_alias=True)
            if run.eval_contract_ref is not None
            else None,
        )
        judge_model = run.judge.model_route
        if (
            (run.tenant.org_id, run.tenant.project_id) != scope.key
            or run.target != target
            or run.status not in {EvalRunStatus.QUEUED, EvalRunStatus.RUNNING}
            or run.eval_contract_ref is None
            or judge_model is None
            or judge_model.asset_type is not AssetType.REGISTERED_MODEL
            or not judge_model.revision.isascii()
            or not judge_model.revision.isdecimal()
            or str(int(judge_model.revision)) != judge_model.revision
            or int(judge_model.revision) < 1
        ):
            raise ValueError("original live contracted Route Run drifted")
        options.append(run)
    if len({run.run_id for run in options}) != len(options):
        raise ValueError("duplicate original Run option")
    if _boundary(conn, expected_database, scope) != evaluated_at:
        raise ValueError("caller transaction changed during Run discovery")
    return options


__all__ = ["list_route_eval_run_options"]
