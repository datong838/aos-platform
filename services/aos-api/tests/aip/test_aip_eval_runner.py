from __future__ import annotations

import importlib.util
import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg import sql

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
)
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetPiiState,
    DatasetRevisionRef,
    DatasetSourceKind,
    EvalCaseDefinition,
    EvalCaseKind,
    EvalDatasetManifest,
    EvalSuiteRevision,
    JudgeRevisionRef,
)
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    ContractReadiness,
    EvalContractRevision,
    ExactRevisionRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_runner import (
    AipEvalRunner,
    JudgeExecution,
    ResolvedArtifact,
    TargetExecution,
    compute_eval_report_hash,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 11, 13, 0, tzinfo=UTC)
H1, H2, H3, H4 = (char * 64 for char in "1234")
SCOPE = TenantScope("org-a", "project-a")
OTHER = TenantScope("org-b", "project-b")


def _migration_tables(path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    return [s for s in statements if s.lstrip().startswith("CREATE TABLE")]


@pytest.fixture()
def runtime():
    schema = f"aip4_runner_{uuid.uuid4().hex}"
    versions = Path(__file__).resolve().parents[2] / "alembic/versions"
    tables: list[str] = []
    for name in (
        "aip4_001_eval_lineage_observability_contract.py",
        "aip4_002_eval_pack_registry.py",
        "aip4_003_eval_report_revision.py",
    ):
        tables.extend(_migration_tables(versions / name))
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute(
                "CREATE TABLE twa_workspace (org_id TEXT,project_id TEXT,PRIMARY KEY(org_id,project_id))"
            )
            conn.execute("INSERT INTO twa_workspace VALUES ('org-a','project-a'),('org-b','project-b')")
            for statement in tables:
                conn.execute(statement)
            conn.execute("ALTER TABLE aip_eval_run ADD COLUMN eval_contract_ref JSONB")
            conn.execute("ALTER TABLE aip_eval_report_revision ADD COLUMN eval_contract_ref JSONB")
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect(_scope: TenantScope | None = None):
        with connect() as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield conn

    registry = AipEvalPackRegistry(connect_factory=scoped_connect)
    runner = AipEvalRunner(connect_factory=scoped_connect)
    _seed(registry)
    yield runner, scoped_connect
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _asset(kind: AssetType, identifier: str, digest: str) -> AssetRevisionRef:
    return AssetRevisionRef(asset_type=kind, asset_id=identifier, revision="1", content_hash=digest)


def _dataset() -> DatasetRevisionRef:
    return DatasetRevisionRef(
        dataset_id="dataset-real", revision=1, content_hash=H1, source_hash=H2,
        redaction_policy=_asset(AssetType.POLICY, "redact", H3),
    )


def _value_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


INPUT_VALUE = {"x": 1}
EXPECTED_VALUE = {"answer": 2}
INPUT = ArtifactRef(artifact_id="input-1", artifact_type="eval_input", revision="1", content_hash=_value_hash(INPUT_VALUE))
EXPECTED = ArtifactRef(artifact_id="expected-1", artifact_type="eval_expected", revision="1", content_hash=_value_hash(EXPECTED_VALUE))
TARGET = _asset(AssetType.LOGIC_GRAPH, "logic-1", H2)
JUDGE = JudgeRevisionRef(judge_id="exact", revision=1, content_hash=H3)


def _suite() -> EvalSuiteRevision:
    suite = EvalSuiteRevision(
        suite_id="suite-1", revision=1, content_hash=H4, target=TARGET,
        dataset=_dataset(), judge=JUDGE,
        cases=[EvalCaseDefinition(case_id="case-1", kind=EvalCaseKind.POSITIVE,
            input_artifact=INPUT, expected_artifact=EXPECTED, timeout_ms=1000)],
        gate_threshold=1.0,
    )
    return suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})


def _seed(registry: AipEvalPackRegistry) -> None:
    manifest = EvalDatasetManifest(
        source_kind=DatasetSourceKind.SELECTION_SNAPSHOT,
        source_id="orders-authoritative-snapshot", source_revision="watermark-1",
        source_hash=H2, fields_allowlist=["order_id", "amount"],
        redaction_receipt=ArtifactRef(artifact_id="redact-1", artifact_type="redaction_receipt", revision="1", content_hash=H4),
        pii_state=DatasetPiiState.REDACTED, case_count=1, captured_at=NOW,
    )
    registry.register_dataset_revision(SCOPE, _dataset(), manifest, actor="user:dev")
    registry.register_suite_revision(SCOPE, _suite(), actor="user:dev")


def _resolver(ref: ArtifactRef) -> ResolvedArtifact:
    values = {INPUT.artifact_id: INPUT_VALUE, EXPECTED.artifact_id: EXPECTED_VALUE}
    return ResolvedArtifact(reference=ref, value=values[ref.artifact_id])


def _target(ref: AssetRevisionRef, value) -> TargetExecution:
    return TargetExecution(target=ref, value={"answer": value["x"] + 1})


def _judge(ref: JudgeRevisionRef, actual, expected) -> JudgeExecution:
    return JudgeExecution(judge=ref, passed=actual == expected, detail_code="exact_match")


def test_runner_persists_hash_only_report_and_terminal_run(runtime) -> None:
    runner, scoped = runtime
    report = runner.run(
        SCOPE, suite_id="suite-1", suite_revision=1, idempotency_key="once-1",
        actor="user:dev", resolve_artifact=_resolver, execute_target=_target, execute_judge=_judge,
    )
    assert report.gate_passed is True
    assert report.content_hash == compute_eval_report_hash(report)
    assert report.results[0].actual_hash == H4 or len(report.results[0].actual_hash) == 64
    assert runner.get_report(SCOPE, report.report_id) == report
    with scoped() as conn:
        row = conn.execute("SELECT status FROM aip_eval_run WHERE run_id=%s", (report.run_id,)).fetchone()
        stored = conn.execute("SELECT results::text AS results FROM aip_eval_report_revision WHERE report_id=%s", (report.report_id,)).fetchone()
    assert row["status"] == "succeeded"
    payload = json.loads(stored["results"])
    assert set(payload[0]) == {
        "caseId", "passed", "actualHash", "expectedHash", "detailCode", "durationMs"
    }


@pytest.mark.parametrize("drift", ["artifact", "artifact_content", "target", "judge"])
def test_runner_fails_closed_on_exact_reference_drift(runtime, drift: str) -> None:
    runner, scoped = runtime

    def resolver(ref):
        resolved = _resolver(ref)
        if drift == "artifact" and ref == INPUT:
            bad = ref.model_copy(update={"content_hash": H4})
            return ResolvedArtifact(reference=bad, value=resolved.value)
        if drift == "artifact_content" and ref == INPUT:
            return ResolvedArtifact(reference=ref, value={"x": 999})
        return resolved

    def target(ref, value):
        result = _target(ref, value)
        return TargetExecution(target=ref.model_copy(update={"content_hash": H4}), value=result.value) if drift == "target" else result

    def judge(ref, actual, expected):
        result = _judge(ref, actual, expected)
        return JudgeExecution(judge=ref.model_copy(update={"content_hash": H4}), passed=result.passed, detail_code=result.detail_code) if drift == "judge" else result

    with pytest.raises(AipEvalAuthorityConflict):
        runner.run(
            SCOPE, suite_id="suite-1", suite_revision=1, idempotency_key=f"drift-{drift}",
            actor="user:dev", resolve_artifact=resolver, execute_target=target, execute_judge=judge,
        )
    with scoped() as conn:
        run = conn.execute("SELECT status FROM aip_eval_run WHERE idempotency_key=%s", (f"drift-{drift}",)).fetchone()
        reports = conn.execute("SELECT count(*) AS n FROM aip_eval_report_revision WHERE run_id IN (SELECT run_id FROM aip_eval_run WHERE idempotency_key=%s)", (f"drift-{drift}",)).fetchone()
    assert run["status"] == "failed"
    assert reports["n"] == 0


def test_report_is_tenant_scoped(runtime) -> None:
    runner, _ = runtime
    report = runner.run(
        SCOPE, suite_id="suite-1", suite_revision=1, idempotency_key="once-tenant",
        actor="user:dev", resolve_artifact=_resolver, execute_target=_target, execute_judge=_judge,
    )
    with pytest.raises(AipEvalAuthorityNotFound):
        runner.get_report(OTHER, report.report_id)


def _contract(*, content_hash: str = H1, readiness: ContractReadiness = ContractReadiness.READY):
    suite = _suite()
    return EvalContractRevision(
        tenant={"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        contract_id="eval-contract-1", revision=2, version=2,
        suite_ref=ExactRevisionRef(resource_type="EvalSuiteRevision", resource_id=suite.suite_id, revision=suite.revision, content_hash=suite.content_hash),
        publication_ref=ExactRevisionRef(resource_type="PublicationEvent", resource_id="publication-event-1", revision=1, content_hash=H2),
        release_gate_ref=ExactRevisionRef(resource_type="ReleaseGateDecision", resource_id="gate-1", revision=1, content_hash=H3),
        artifact_schema_ref={"resourceType":"Schema","resourceId":"artifact","revision":"1","authority":"aip"},
        severity_thresholds={"critical": 1.0}, gate_policy={"mode":"all"},
        return_mapping={"failed":"review"}, override_policy={"allowed":False},
        content_hash=content_hash, lifecycle=BriefLifecycle.FROZEN,
        readiness=readiness, blockers=[], created_by="user:dev", created_at=NOW,
    )


def test_runner_binds_exact_eval_contract_to_run_and_report(runtime) -> None:
    runner, scoped = runtime
    contract = _contract()

    class Contracts:
        def get_eval_contract(self, scope, contract_id, revision):
            assert scope == SCOPE and contract_id == contract.contract_id and revision == 2
            return contract

    runner._contracts = Contracts()
    report = runner.run_by_contract(
        SCOPE, contract_id=contract.contract_id, contract_revision=2,
        contract_content_hash=contract.content_hash, idempotency_key="contract-once",
        actor="user:dev", resolve_artifact=_resolver, execute_target=_target,
        execute_judge=_judge,
    )
    assert report.eval_contract_ref is not None
    assert report.eval_contract_ref.resource_id == contract.contract_id
    assert runner.get_report(SCOPE, report.report_id).eval_contract_ref == report.eval_contract_ref
    with scoped() as conn:
        run = conn.execute("SELECT eval_contract_ref FROM aip_eval_run WHERE run_id=%s", (report.run_id,)).fetchone()
    assert run["eval_contract_ref"]["contentHash"] == contract.content_hash

    with pytest.raises(AipEvalAuthorityConflict, match="idempotency key was reused"):
        runner.run_by_contract(
            SCOPE, contract_id=contract.contract_id, contract_revision=2,
            contract_content_hash=contract.content_hash, idempotency_key="contract-once",
            actor="user:dev", resolve_artifact=_resolver, execute_target=_target,
            execute_judge=_judge,
        )
    with scoped() as conn:
        replay_count = conn.execute(
            "SELECT count(*) AS n FROM aip_eval_run WHERE idempotency_key='contract-once'"
        ).fetchone()
    assert replay_count["n"] == 1


def test_runner_rejects_eval_contract_hash_drift_before_creating_run(runtime) -> None:
    runner, scoped = runtime
    contract = _contract()

    class Contracts:
        def get_eval_contract(self, *_args):
            return contract

    runner._contracts = Contracts()
    with pytest.raises(AipEvalAuthorityConflict, match="content hash drifted"):
        runner.run_by_contract(
            SCOPE, contract_id=contract.contract_id, contract_revision=2,
            contract_content_hash=H4, idempotency_key="contract-drift",
            actor="user:dev", resolve_artifact=_resolver, execute_target=_target,
            execute_judge=_judge,
        )
    with scoped() as conn:
        count = conn.execute("SELECT count(*) AS n FROM aip_eval_run WHERE idempotency_key='contract-drift'").fetchone()
    assert count["n"] == 0
