"""Read one current, formally published content Eval gate in one tenant transaction."""

from __future__ import annotations

from typing import Any

from aos_api.aip_contracts import ExactContractRef
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_logic_graph_models import compute_logic_graph_hash
from aos_api.aip_logic_graph_store import LogicGraphIntegrityError, LogicGraphStore
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractError, canonical_hash,
)
from aos_api.aip_production_contracts import (
    BriefLifecycle, ContractReadiness, CreateEvalContractRequest,
)
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.ecommerce_content_pre_review_eval import (
    GRAPH_ID, build_content_pre_review_graph,
)
from aos_api.ecommerce_content_pre_review_pack import build_content_pre_review_eval_packs
from aos_api.tenant_scope import TenantScope


def _exact_suite(conn: Any, scope: TenantScope, expected: Any) -> None:
    row = conn.execute(
        """SELECT * FROM aip_eval_suite_revision
            WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
        (*scope.key, expected.suite_id, expected.revision),
    ).fetchone()
    if row is None:
        raise ValueError("content pre-review Suite is missing")
    suite = AipEvalPackRegistry._suite_from_row(row)
    if suite != expected or compute_eval_suite_hash(suite) != suite.content_hash:
        raise ValueError("content pre-review Suite revision or hash drifted")


def require_current_content_pre_review_gate(
    transaction: Any, scope: TenantScope,
) -> ExactContractRef:
    """Resolve a new Plan's gate; never infer authority from arbitrary READY rows.

    The caller supplies one scoped transaction. This reader writes nothing and
    does not register, publish or evaluate a content Artifact.
    """
    if type(scope) is not TenantScope:
        raise ValueError("content Eval requires an exact tenant scope")
    rows = transaction.execute(
        """SELECT h.contract_id,h.current_revision
             FROM aip_eval_contract_head h
             JOIN aip_eval_contract_revision r
               ON r.org_id=h.org_id AND r.project_id=h.project_id
              AND r.contract_id=h.contract_id AND r.revision=h.current_revision
            WHERE h.org_id=%s AND h.project_id=%s
              AND r.gate_policy->>'subjectKind'='ecommerce_content'
            ORDER BY h.contract_id LIMIT 2""",
        scope.key,
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("content pre-review EvalContract absent or ambiguous")
    try:
        contract = AipProductionContractStore().get_eval_contract(
            scope, rows[0]["contract_id"], rows[0]["current_revision"], conn=transaction,
        )
    except ProductionContractError as exc:
        raise ValueError("content pre-review EvalContract unavailable") from exc
    contract_payload = CreateEvalContractRequest(
        suite_ref=contract.suite_ref,
        publication_ref=contract.publication_ref,
        release_gate_ref=contract.release_gate_ref,
        artifact_schema_ref=contract.artifact_schema_ref,
        severity_thresholds=contract.severity_thresholds,
        gate_policy=contract.gate_policy,
        return_mapping=contract.return_mapping,
        override_policy=contract.override_policy,
    )
    if canonical_hash(contract_payload.model_dump(mode="json", by_alias=True)) != contract.content_hash:
        raise ValueError("content pre-review EvalContract content hash drifted")
    if (
        contract.lifecycle is not BriefLifecycle.FROZEN
        or contract.readiness is not ContractReadiness.READY
        or contract.blockers
        or contract.gate_policy.get("subjectKind") != "ecommerce_content"
        or contract.gate_policy.get("subjectInputMode") != "ecommerce-readable-content/v1"
        or contract.gate_policy.get("requiresHumanDecision") is not True
        or contract.override_policy.get("allowed") is not False
        or contract.return_mapping.get("critical") != "content_generate"
        or contract.suite_ref.resource_type != "EvalSuiteRevision"
        or contract.publication_ref is None
        or contract.release_gate_ref is None
    ):
        raise ValueError("content pre-review EvalContract is not the current human-review contract")
    graph_row = transaction.execute(
        """SELECT graph_id,name,description,status,schema_version,revision,
                  published_version,graph_hash,payload,created_at,updated_at,deleted_at
             FROM aip_logic_graph WHERE org_id=%s AND project_id=%s AND graph_id=%s""",
        (*scope.key, GRAPH_ID),
    ).fetchone()
    if graph_row is None or graph_row["deleted_at"] is not None:
        raise ValueError("content pre-review Graph is missing or deleted")
    try:
        graph = LogicGraphStore._snapshot_from_current_row(graph_row)
    except (ValueError, LogicGraphIntegrityError) as exc:
        raise ValueError("content pre-review Graph checksum drifted") from exc
    spec = build_content_pre_review_graph()
    if (
        graph.status != "draft" or graph.graph_hash != compute_logic_graph_hash(spec)
        or graph.name != spec.name or graph.description != spec.description
        or graph.nodes != spec.nodes or graph.edges != spec.edges
        or graph.entry_node_ids != spec.entry_node_ids
    ):
        raise ValueError("content pre-review Graph is not the reviewed current revision")
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH, asset_id=graph.id,
        revision=str(graph.revision), content_hash=graph.graph_hash,
    )
    governance, subject = build_content_pre_review_eval_packs(target)
    _exact_suite(transaction, scope, governance.suite)
    _exact_suite(transaction, scope, subject.suite)
    if (
        contract.suite_ref.resource_id != subject.suite.suite_id
        or contract.suite_ref.revision != subject.suite.revision
        or contract.suite_ref.content_hash != subject.suite.content_hash
    ):
        raise ValueError("content pre-review contract did not bind the subject Suite")
    gate_row = transaction.execute(
        """SELECT * FROM aip_release_gate_decision
            WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
        (*scope.key, contract.release_gate_ref.resource_id),
    ).fetchone()
    event_row = transaction.execute(
        """SELECT * FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s AND event_id=%s""",
        (*scope.key, contract.publication_ref.resource_id),
    ).fetchone()
    clock = transaction.execute("SELECT clock_timestamp() AS now").fetchone()
    if gate_row is None or event_row is None or clock is None:
        raise ValueError("content pre-review release authority is missing")
    gate = AipReleasePublicationService._gate_from_row(scope, gate_row)
    now = clock["now"]
    if (
        contract.release_gate_ref.content_hash != gate.decision_hash
        or gate.status.value != "passed" or gate.invalidated_by is not None
        or not gate.decided_at <= now < gate.expires_at
        or gate.target != target
        or gate.suite_ref.asset_type is not AssetType.EVAL_SUITE
        or gate.suite_ref.asset_id != governance.suite.suite_id
        or gate.suite_ref.revision != str(governance.suite.revision)
        or gate.suite_ref.content_hash != governance.suite.content_hash
    ):
        raise ValueError("content pre-review governance release gate drifted or expired")
    if (
        contract.publication_ref.content_hash
        != canonical_hash(AipProductionContractStore._publication_snapshot(event_row))
        or event_row["event_type"] != "published"
        or event_row["occurred_at"] > now
        or event_row["release_gate_decision_id"] != gate.decision_id
        or AssetRevisionRef.model_validate(event_row["target_ref"]) != target
    ):
        raise ValueError("content pre-review publication lineage drifted")
    latest = transaction.execute(
        """SELECT event_id,event_type FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s AND publication_id=%s
            ORDER BY occurred_at DESC,event_id DESC LIMIT 1""",
        (*scope.key, event_row["publication_id"]),
    ).fetchone()
    if latest is None or (latest["event_id"], latest["event_type"]) != (
        event_row["event_id"], "published"
    ):
        raise ValueError("content pre-review publication is no longer current")
    try:
        AipReleasePublicationService._verify_gate_evidence(transaction, scope, gate)
    except Exception as exc:
        raise ValueError("content pre-review governance report drifted") from exc
    report_row = transaction.execute(
        """SELECT * FROM aip_eval_report_revision
            WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
        (*scope.key, gate.eval_report.artifact_id, int(gate.eval_report.revision)),
    ).fetchone()
    run_row = transaction.execute(
        """SELECT * FROM aip_eval_run
            WHERE org_id=%s AND project_id=%s AND run_id=%s""",
        (*scope.key, gate.eval_run_id),
    ).fetchone()
    if report_row is None or run_row is None:
        raise ValueError("content pre-review governance Eval evidence is missing")
    report = AipReleasePublicationService._report_from_row(scope, report_row)
    try:
        AipReleasePublicationService._verify_run(report, run_row)
    except Exception as exc:
        raise ValueError("content pre-review governance Eval run drifted") from exc
    results = {item.case_id: item for item in report.results}
    expected = {
        case.case_id: case.expected_artifact.content_hash
        for case in governance.suite.cases if case.expected_artifact is not None
    }
    if (
        not report.gate_passed or report.passed != len(governance.suite.cases)
        or report.failed != 0 or len(results) != len(governance.suite.cases)
        or report.subject_artifact_ref is not None
        or report.eval_contract_ref is not None
        or any(
            case_id not in results or not results[case_id].passed
            or results[case_id].actual_hash != digest
            or results[case_id].expected_hash != digest
            for case_id, digest in expected.items()
        )
    ):
        raise ValueError("content pre-review governance cases did not all pass")
    return ExactContractRef(
        resource_type="EvalContractRevision", resource_id=contract.contract_id,
        revision=contract.revision, content_hash=contract.content_hash,
    )
