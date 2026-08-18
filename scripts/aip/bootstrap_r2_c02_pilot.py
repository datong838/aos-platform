#!/usr/bin/env python3
"""Persist the approved C02 Logic/Eval/Publication chain for R2.

Dry-run is the default.  ``--apply`` writes only the C02 graph, its isolated
contract Eval evidence, one canonical dry-run history row and one immutable
Logic publication.  It never resolves a Secret, calls a Provider, creates a
Binding or creates an AgentRun.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_c02_pilot import (
    C02_EVAL_SUITE_ID,
    C02_GRAPH_ID,
    build_c02_graph_request,
    evaluate_c02_contract,
)
from aos_api.aip_eval_models import EvalReportEvidence
from aos_api.aip_eval_store import (
    EvalConflict,
    EvalEvidenceStore,
    EvalNotFound,
    LogicEvalEvidenceReader,
)
from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest, LogicTokenUsage
from aos_api.aip_logic_graph_models import (
    logic_graph_content_payload,
)
from aos_api.aip_logic_graph_store import (
    LogicGraphConflict,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.aip_logic_publication_models import PublishLogicGraphRequest
from aos_api.aip_logic_publication_store import LogicPublicationStore
from aos_api.aip_logic_run_store import LogicRunStore
from aos_api.aip_logic_runtime_adapters import (
    LLMAdapterResult,
    LogicAdapterError,
    RuntimeAdapterRegistry,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-c02-bootstrap"
APPROVAL_REF = "46-R2-C02-CONTENT-OFFICER"
MODEL_ID = "model-qyh-text-dev"
MODEL_REVISION = 3
REQUIRED_ALEMBIC_HEAD = "aip10_006"


def exact_model_alias(model: Any) -> str:
    return (
        f"RegisteredModelRevision:{model.registered_model_id}"
        f"@{model.revision}#{model.content_hash}"
    )


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "steps": [
            "require aip10_005",
            "read exact RegisteredModelRevision",
            "persist C02 graph revision",
            "run six isolated contract cases",
            "persist canonical successful dry-run",
            "persist Eval suite/report",
            "publish immutable Logic revision",
            "verify negative-tenant canary",
        ],
        "forbiddenSideEffects": [
            "Secret payload read",
            "Provider call",
            "CapabilityBinding",
            "SkillBinding",
            "AgentRun",
        ],
    }


def _require_schema_head() -> None:
    with db_connect(SCOPE) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    current = str(row["version_num"]) if row else ""
    if current != REQUIRED_ALEMBIC_HEAD:
        raise RuntimeError(
            f"schema head must be {REQUIRED_ALEMBIC_HEAD}; current={current or 'missing'}"
        )


def _isolated_registry(model_alias: str) -> RuntimeAdapterRegistry:
    registry = RuntimeAdapterRegistry(max_concurrency=1)

    def invoke(prompt, context):
        context.checkpoint()
        if "__simulate_adapter_error__" in prompt:
            raise LogicAdapterError(
                "LLM_ADAPTER_FAILED", "isolated C02 adapter failure"
            )
        return LLMAdapterResult(
            output="isolated C02 contract draft; not Provider quality evidence",
            usage=LogicTokenUsage(
                model=model_alias,
                input_tokens=16,
                output_tokens=8,
                total_tokens=24,
            ),
        )

    registry.register_llm(
        model_alias,
        invoke,
        adapter_name="d03-isolated-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def _get_or_create_graph(model_alias: str):
    store = LogicGraphStore()
    request = build_c02_graph_request(model_id=model_alias)
    expected = logic_graph_content_payload(request)
    try:
        graph = store.get(SCOPE.org_id, SCOPE.project_id, C02_GRAPH_ID)
    except LogicGraphNotFound:
        try:
            return store.create(SCOPE.org_id, SCOPE.project_id, ACTOR, request)
        except LogicGraphConflict as exc:
            raise RuntimeError("C02 graph was created concurrently") from exc
    actual = graph.model_dump(
        mode="json",
        include={
            "name",
            "description",
            "status",
            "schema_version",
            "nodes",
            "edges",
            "entry_node_ids",
        },
    )
    if actual != expected:
        raise RuntimeError("existing C02 graph differs from the approved exact graph")
    return graph


def _persist_successful_run(graph, registry, inputs) -> str:
    request = LogicDryRunRequest(
        expected_revision=graph.revision,
        dry_run=True,
        expected_graph_hash=graph.graph_hash,
        inputs=inputs,
        idempotency_key=f"{APPROVAL_REF}-logic-dry-run-r{graph.revision}",
    )
    run_store = LogicRunStore()
    start = run_store.start_run(
        SCOPE.org_id,
        SCOPE.project_id,
        ACTOR,
        graph,
        request,
        f"logic-run-d03-{uuid.uuid4().hex}",
    )
    if start.replay is not None:
        if start.replay.status != "succeeded":
            raise RuntimeError("existing canonical C02 dry-run did not succeed")
        return start.replay.run_id
    assert start.started_at is not None
    result = LogicDryRunExecutor(registry).execute_guarded(
        graph,
        inputs,
        run_id=start.run_id,
        started_at=start.started_at,
    )
    run_store.finalize_run(SCOPE.org_id, SCOPE.project_id, result)
    if result.status != "succeeded" or result.production_written is not False:
        raise RuntimeError("canonical C02 dry-run failed closed")
    return result.run_id


def _persist_eval(graph, registry) -> tuple[EvalReportEvidence, str]:
    evaluated = evaluate_c02_contract(graph, registry, now=datetime.now(UTC))
    store = EvalEvidenceStore()
    try:
        persisted_suite = store.get_suite(
            SCOPE.org_id, SCOPE.project_id, evaluated.suite.id
        )
    except EvalNotFound:
        try:
            persisted_suite = store.create_suite(
                SCOPE.org_id, SCOPE.project_id, ACTOR, evaluated.suite
            )
        except EvalConflict as exc:
            raise RuntimeError("C02 Eval suite was created concurrently") from exc
    if persisted_suite.model_dump(mode="json") != evaluated.suite.model_dump(mode="json"):
        raise RuntimeError("persisted C02 Eval suite drifted")

    try:
        report = store.get_report(
            SCOPE.org_id, SCOPE.project_id, evaluated.report.report_id
        )
    except EvalNotFound:
        report = store.save_report(
            SCOPE.org_id, SCOPE.project_id, ACTOR, evaluated.report
        )
    expected_target = (
        graph.id,
        graph.revision,
        graph.graph_hash,
        len(evaluated.suite.cases),
    )
    actual_target = (
        report.target_id,
        report.target_revision,
        report.target_hash,
        report.total,
    )
    if actual_target != expected_target or not report.gate_passed:
        raise RuntimeError("persisted C02 Eval report does not match exact graph")
    positive = next(
        case.inputs for case in evaluated.suite.cases if case.id == "d03-positive"
    )
    run_id = _persist_successful_run(graph, registry, positive)
    return report, run_id


def _negative_canary_counts() -> dict[str, int]:
    with db_connect(CANARY_SCOPE) as conn:
        return {
            table: int(
                conn.execute(
                    f"SELECT COUNT(*) AS count FROM {table} "
                    "WHERE org_id=%s AND project_id=%s AND "
                    + (
                        "graph_id=%s"
                        if table != "aip_eval_suite"
                        else "suite_id=%s"
                    ),
                    (
                        *CANARY_SCOPE.key,
                        C02_GRAPH_ID
                        if table != "aip_eval_suite"
                        else C02_EVAL_SUITE_ID,
                    ),
                ).fetchone()["count"]
            )
            for table in (
                "aip_logic_graph",
                "aip_logic_publication",
                "aip_eval_suite",
            )
        }


def apply() -> dict[str, Any]:
    _require_schema_head()
    before_canary = _negative_canary_counts()
    if any(before_canary.values()):
        raise RuntimeError("negative tenant canary already contains C02 authority")
    model = AipModelRuntimeStore().get_model(SCOPE, MODEL_ID, MODEL_REVISION)
    model_alias = exact_model_alias(model)
    graph = _get_or_create_graph(model_alias)
    registry = _isolated_registry(model_alias)
    report, run_id = _persist_eval(graph, registry)
    publication = LogicPublicationStore().publish(
        SCOPE.org_id,
        SCOPE.project_id,
        ACTOR,
        graph.id,
        PublishLogicGraphRequest(
            expected_revision=graph.revision,
            expected_graph_hash=graph.graph_hash,
            eval_suite_id=report.suite_id,
            eval_report_id=report.report_id,
            idempotency_key=f"{APPROVAL_REF}-logic-publication-r{graph.revision}",
        ),
        LogicEvalEvidenceReader(),
    )
    after_canary = _negative_canary_counts()
    if after_canary != before_canary:
        raise RuntimeError("C02 authority leaked into the negative tenant canary")
    return {
        "status": "C02_LOGIC_PUBLICATION_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "graph": {
            "assetId": graph.id,
            "revision": graph.revision,
            "contentHash": graph.graph_hash,
        },
        "model": {
            "assetId": model.registered_model_id,
            "revision": model.revision,
            "contentHash": model.content_hash,
        },
        "eval": {
            "suiteId": report.suite_id,
            "reportId": report.report_id,
            "passed": report.passed,
            "total": report.total,
            "isolatedContractOnly": True,
        },
        "dryRunId": run_id,
        "publicationId": publication.publication_id,
        "negativeCanaryCounts": after_canary,
        "providerCalls": 0,
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else build_plan()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
