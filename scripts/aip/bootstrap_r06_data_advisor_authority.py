#!/usr/bin/env python3
"""Plan or persist the missing R06 data-advisor Logic authority chain.

The default invocation is read-only. ``--apply`` writes only D01/D02/D04/D05/D06
Graph revisions, isolated contract Eval evidence, canonical dry-run rows and
immutable Logic publications. It never resolves a Secret, calls a Provider,
creates a Binding, creates an AgentRun or executes a production Action. D03 is
treated as immutable pre-existing authority and is verified before and after.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))

from aos_api.aip_data_advisor_logic import (  # noqa: E402
    DATA_ADVISOR_LOGIC_IDS,
    build_data_advisor_graph_request,
    data_advisor_definition,
    evaluate_data_advisor_contract,
)
from aos_api.aip_eval_models import EvalReportEvidence  # noqa: E402
from aos_api.aip_eval_store import (  # noqa: E402
    EvalConflict,
    EvalEvidenceStore,
    EvalNotFound,
    LogicEvalEvidenceReader,
)
from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor  # noqa: E402
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest, LogicTokenUsage  # noqa: E402
from aos_api.aip_logic_graph_models import logic_graph_content_payload  # noqa: E402
from aos_api.aip_logic_graph_store import (  # noqa: E402
    LogicGraphConflict,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.aip_logic_publication_models import PublishLogicGraphRequest  # noqa: E402
from aos_api.aip_logic_publication_store import LogicPublicationStore  # noqa: E402
from aos_api.aip_logic_run_store import LogicRunStore  # noqa: E402
from aos_api.aip_logic_runtime_adapters import (  # noqa: E402
    LLMAdapterResult,
    LogicAdapterError,
    RuntimeAdapterRegistry,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r06-data-advisor-bootstrap"
APPROVAL_REF = "130-R06-DATA-ADVISOR-AUTHORIZED"
MODEL_ID = "model-qyh-text-dev"
REQUIRED_ALEMBIC_HEAD = "aip13_001"
D03_GRAPH_ID = "ecommerce.logic.D03"


def exact_model_alias(model: Any) -> str:
    return (
        f"RegisteredModelRevision:{model.registered_model_id}"
        f"@{model.revision}#{model.content_hash}"
    )


def build_plan() -> dict[str, object]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "negativeCanary": {
            "orgId": CANARY_SCOPE.org_id,
            "projectId": CANARY_SCOPE.project_id,
        },
        "logicIds": list(DATA_ADVISOR_LOGIC_IDS),
        "preservedAuthority": [D03_GRAPH_ID],
        "steps": [
            f"require exact schema head {REQUIRED_ALEMBIC_HEAD}",
            "read current active exact text model alias without resolving Secret payload",
            "snapshot immutable D03 Graph and publications",
            "persist five missing Graph revisions",
            "run six isolated contract cases per Logic",
            "persist successful dry-run and Eval evidence",
            "publish five immutable Logic revisions",
            "verify D03 unchanged and negative canary remains empty",
        ],
        "providerCalls": 0,
        "agentRuns": 0,
        "productionWrites": 0,
        "forbiddenSideEffects": [
            "Secret payload read",
            "Provider call",
            "Provider Health mutation",
            "CapabilityBinding",
            "SkillBinding",
            "AgentRun",
            "production Action",
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
                "LLM_ADAPTER_FAILED", "isolated data-advisor adapter failure"
            )
        return LLMAdapterResult(
            output="isolated data-advisor contract draft; not Provider quality evidence",
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
        adapter_name="r06-data-advisor-isolated-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def _get_or_create_graph(logic_id: str, model_alias: str):
    definition = data_advisor_definition(logic_id)
    store = LogicGraphStore()
    request = build_data_advisor_graph_request(logic_id, model_id=model_alias)
    expected = logic_graph_content_payload(request)
    try:
        graph = store.get(SCOPE.org_id, SCOPE.project_id, definition.graph_id)
    except LogicGraphNotFound:
        try:
            return store.create(SCOPE.org_id, SCOPE.project_id, ACTOR, request)
        except LogicGraphConflict as exc:
            raise RuntimeError(f"{logic_id} graph was created concurrently") from exc
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
        raise RuntimeError(
            f"existing {logic_id} graph differs from the approved exact graph"
        )
    return graph


def _persist_successful_run(logic_id: str, graph, registry, inputs) -> str:
    request = LogicDryRunRequest(
        expected_revision=graph.revision,
        dry_run=True,
        expected_graph_hash=graph.graph_hash,
        inputs=inputs,
        idempotency_key=(
            f"{APPROVAL_REF}-{logic_id.lower()}-logic-dry-run-r{graph.revision}"
        ),
    )
    run_store = LogicRunStore()
    start = run_store.start_run(
        SCOPE.org_id,
        SCOPE.project_id,
        ACTOR,
        graph,
        request,
        f"logic-run-{logic_id.lower()}-{uuid.uuid4().hex}",
    )
    if start.replay is not None:
        if start.replay.status != "succeeded":
            raise RuntimeError(f"existing canonical {logic_id} dry-run did not succeed")
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
        raise RuntimeError(f"canonical {logic_id} dry-run failed closed")
    return result.run_id


def _persist_eval(logic_id: str, graph, registry) -> tuple[EvalReportEvidence, str]:
    evaluated = evaluate_data_advisor_contract(
        logic_id, graph, registry, now=datetime.now(UTC)
    )
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
            raise RuntimeError(
                f"{logic_id} Eval suite was created concurrently"
            ) from exc
    if persisted_suite.model_dump(mode="json") != evaluated.suite.model_dump(mode="json"):
        raise RuntimeError(f"persisted {logic_id} Eval suite drifted")

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
        raise RuntimeError(f"persisted {logic_id} Eval report does not match exact graph")
    positive = next(
        case.inputs
        for case in evaluated.suite.cases
        if case.id == f"{logic_id.lower()}-positive"
    )
    return report, _persist_successful_run(logic_id, graph, registry, positive)


def _d03_snapshot() -> dict[str, Any]:
    graph = LogicGraphStore().get(SCOPE.org_id, SCOPE.project_id, D03_GRAPH_ID)
    publications = LogicPublicationStore().list(
        SCOPE.org_id, SCOPE.project_id, D03_GRAPH_ID
    )
    return {
        "graphRevision": graph.revision,
        "graphHash": graph.graph_hash,
        "publishedVersion": graph.published_version,
        "publicationRefs": [
            {
                "publicationId": item.publication_id,
                "revision": item.graph_revision,
                "graphHash": item.graph_hash,
            }
            for item in publications.items
        ],
    }


def _negative_canary_counts() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    with db_connect(CANARY_SCOPE) as conn:
        for logic_id in DATA_ADVISOR_LOGIC_IDS:
            definition = data_advisor_definition(logic_id)
            result[logic_id] = {
                "graph": int(
                    conn.execute(
                        "SELECT COUNT(*) AS count FROM aip_logic_graph "
                        "WHERE org_id=%s AND project_id=%s AND graph_id=%s",
                        (*CANARY_SCOPE.key, definition.graph_id),
                    ).fetchone()["count"]
                ),
                "publication": int(
                    conn.execute(
                        "SELECT COUNT(*) AS count FROM aip_logic_publication "
                        "WHERE org_id=%s AND project_id=%s AND graph_id=%s",
                        (*CANARY_SCOPE.key, definition.graph_id),
                    ).fetchone()["count"]
                ),
                "evalSuite": int(
                    conn.execute(
                        "SELECT COUNT(*) AS count FROM aip_eval_suite "
                        "WHERE org_id=%s AND project_id=%s AND suite_id=%s",
                        (*CANARY_SCOPE.key, definition.eval_suite_id),
                    ).fetchone()["count"]
                ),
            }
    return result


def apply() -> dict[str, Any]:
    _require_schema_head()
    before_canary = _negative_canary_counts()
    if any(value for counts in before_canary.values() for value in counts.values()):
        raise RuntimeError("negative tenant canary already contains R06 authority")
    d03_before = _d03_snapshot()
    model = AipModelRuntimeStore().get_model(SCOPE, MODEL_ID)
    if model.lifecycle.value != "active":
        raise RuntimeError("current exact text model is not active")
    model_alias = exact_model_alias(model)
    registry = _isolated_registry(model_alias)
    persisted: list[dict[str, Any]] = []
    for logic_id in DATA_ADVISOR_LOGIC_IDS:
        graph = _get_or_create_graph(logic_id, model_alias)
        report, run_id = _persist_eval(logic_id, graph, registry)
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
                idempotency_key=(
                    f"{APPROVAL_REF}-{logic_id.lower()}-publication-r{graph.revision}"
                ),
            ),
            LogicEvalEvidenceReader(),
        )
        persisted.append(
            {
                "logicId": logic_id,
                "graphId": graph.id,
                "revision": graph.revision,
                "graphHash": graph.graph_hash,
                "evalSuiteId": report.suite_id,
                "evalReportId": report.report_id,
                "evalPassed": report.passed,
                "evalTotal": report.total,
                "dryRunId": run_id,
                "publicationId": publication.publication_id,
            }
        )
    d03_after = _d03_snapshot()
    if d03_after != d03_before:
        raise RuntimeError("immutable D03 authority changed during R06 bootstrap")
    after_canary = _negative_canary_counts()
    if after_canary != before_canary:
        raise RuntimeError("R06 authority leaked into the negative tenant canary")
    return {
        "status": "R06_DATA_ADVISOR_LOGIC_AUTHORITY_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "model": {
            "assetId": model.registered_model_id,
            "revision": model.revision,
            "contentHash": model.content_hash,
        },
        "logic": persisted,
        "d03Preserved": d03_after,
        "negativeCanaryCounts": after_canary,
        "providerCalls": 0,
        "agentRuns": 0,
        "productionWrites": 0,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = apply() if args.apply else build_plan()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
