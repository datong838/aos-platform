from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg import sql
from pydantic import ValidationError

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
from aos_api.aip_eval_pack_registry import (
    AipEvalPackRegistry,
    compute_eval_suite_hash,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
H1, H2, H3, H4 = (char * 64 for char in "1234")
SCOPE_A = TenantScope("org-a", "project-a")
SCOPE_B = TenantScope("org-b", "project-b")


def _load_create_tables(path: Path) -> list[str]:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements: list[str] = []
    with patch.object(migration.op, "execute", statements.append):
        migration.upgrade()
    return [
        statement
        for statement in statements
        if statement.lstrip().startswith("CREATE TABLE")
    ]


@pytest.fixture()
def registry():
    schema = f"aip4_registry_{uuid.uuid4().hex}"
    versions = Path(__file__).resolve().parents[2] / "alembic/versions"
    tables = _load_create_tables(
        versions / "aip4_001_eval_lineage_observability_contract.py"
    ) + _load_create_tables(versions / "aip4_002_eval_pack_registry.py")
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute(
                """CREATE TABLE twa_workspace (
                   org_id TEXT NOT NULL,project_id TEXT NOT NULL,
                   PRIMARY KEY (org_id,project_id))"""
            )
            conn.execute(
                "INSERT INTO twa_workspace VALUES ('org-a','project-a'),('org-b','project-b')"
            )
            for statement in tables:
                conn.execute(statement)
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect(_scope: TenantScope | None = None):
        with connect() as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield conn

    yield AipEvalPackRegistry(connect_factory=scoped_connect)
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _asset(kind: AssetType, identifier: str, digest: str = H1) -> AssetRevisionRef:
    return AssetRevisionRef(
        asset_type=kind, asset_id=identifier, revision="1", content_hash=digest
    )


def _dataset() -> DatasetRevisionRef:
    return DatasetRevisionRef(
        dataset_id="dataset-real-1",
        revision=1,
        content_hash=H1,
        source_hash=H2,
        redaction_policy=_asset(AssetType.POLICY, "redaction-policy", H3),
    )


def _manifest(source_id: str = "object-selection-orders-20260811") -> EvalDatasetManifest:
    return EvalDatasetManifest(
        source_kind=DatasetSourceKind.SELECTION_SNAPSHOT,
        source_id=source_id,
        source_revision="watermark-2026-08-11T12:00:00Z",
        source_hash=H2,
        fields_allowlist=["order_id", "order_status", "total_amount"],
        redaction_receipt=ArtifactRef(
            artifact_id="redaction-receipt-1",
            artifact_type="redaction_receipt",
            revision="1",
            content_hash=H4,
        ),
        pii_state=DatasetPiiState.REDACTED,
        case_count=12,
        captured_at=NOW,
    )


def _suite(content_hash: str = H4) -> EvalSuiteRevision:
    suite = EvalSuiteRevision(
        suite_id="logic-order-health",
        revision=1,
        content_hash=content_hash,
        target=_asset(AssetType.LOGIC_GRAPH, "logic-order-health", H2),
        dataset=_dataset(),
        judge=JudgeRevisionRef(judge_id="exact-v1", revision=1, content_hash=H3),
        cases=[
            EvalCaseDefinition(
                case_id="positive-1",
                kind=EvalCaseKind.POSITIVE,
                input_artifact=ArtifactRef(
                    artifact_id="case-input-1",
                    artifact_type="eval_case_input",
                    revision="1",
                    content_hash=H1,
                ),
                expected_artifact=ArtifactRef(
                    artifact_id="case-expected-1",
                    artifact_type="eval_case_expected",
                    revision="1",
                    content_hash=H2,
                ),
                timeout_ms=1000,
            )
        ],
        gate_threshold=1.0,
    )
    return suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})


def test_manifest_rejects_mock_and_inline_rows() -> None:
    with pytest.raises(ValidationError):
        _manifest("mock-orders")
    with pytest.raises(ValidationError):
        EvalDatasetManifest.model_validate(
            {**_manifest().model_dump(mode="json"), "rows": [{"mobile": "13800000000"}]}
        )


def test_register_dataset_and_suite_is_idempotent(registry: AipEvalPackRegistry) -> None:
    dataset = registry.register_dataset_revision(
        SCOPE_A, _dataset(), _manifest(), actor="user:dev"
    )
    assert dataset == _dataset()
    suite = _suite()
    assert registry.register_suite_revision(SCOPE_A, suite, actor="user:dev") == suite
    assert registry.register_suite_revision(SCOPE_A, suite, actor="user:dev") == suite
    assert registry.get_suite_revision(SCOPE_A, suite.suite_id, 1) == suite


def test_suite_requires_existing_exact_dataset(registry: AipEvalPackRegistry) -> None:
    with pytest.raises(AipEvalAuthorityNotFound):
        registry.register_suite_revision(SCOPE_A, _suite(), actor="user:dev")
    registry.register_dataset_revision(SCOPE_A, _dataset(), _manifest(), actor="user:dev")
    drifted = _suite().model_copy(
        update={"dataset": _dataset().model_copy(update={"source_hash": H4})}
    )
    drifted = drifted.model_copy(update={"content_hash": compute_eval_suite_hash(drifted)})
    with pytest.raises(AipEvalAuthorityConflict):
        registry.register_suite_revision(SCOPE_A, drifted, actor="user:dev")


def test_suite_hash_and_revision_conflicts_fail_closed(registry: AipEvalPackRegistry) -> None:
    registry.register_dataset_revision(SCOPE_A, _dataset(), _manifest(), actor="user:dev")
    with pytest.raises(ValueError, match="canonical"):
        registry.register_suite_revision(
            SCOPE_A, _suite().model_copy(update={"content_hash": H4}), actor="user:dev"
        )
    original = _suite()
    registry.register_suite_revision(SCOPE_A, original, actor="user:dev")
    changed = original.model_copy(update={"gate_threshold": 0.5})
    changed = changed.model_copy(update={"content_hash": compute_eval_suite_hash(changed)})
    with pytest.raises(AipEvalAuthorityConflict):
        registry.register_suite_revision(SCOPE_A, changed, actor="user:dev")


def test_cross_tenant_registry_is_empty(registry: AipEvalPackRegistry) -> None:
    registry.register_dataset_revision(SCOPE_A, _dataset(), _manifest(), actor="user:dev")
    suite = _suite()
    registry.register_suite_revision(SCOPE_A, suite, actor="user:dev")
    assert registry.list_suite_revisions(SCOPE_B) == []
    with pytest.raises(AipEvalAuthorityNotFound):
        registry.get_suite_revision(SCOPE_B, suite.suite_id, suite.revision)
