"""PostgreSQL store for tenant-scoped Evals suites and immutable reports."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_eval_models import (
    EvalReportEvidence,
    LogicEvalEvidence,
    LogicGraphEvalTarget,
)
from aos_api.db import connect as db_connect
from aos_api.evals_engine import EvalSuite, TestCase

ConnectFactory = Callable[[], AbstractContextManager[Any]]


class EvalStoreError(RuntimeError):
    code = "EVAL_STORE_ERROR"


class EvalNotFound(EvalStoreError):
    code = "EVAL_NOT_FOUND"


class EvalConflict(EvalStoreError):
    code = "EVAL_CONFLICT"


class EvalTargetNotFound(EvalStoreError):
    code = "EVAL_TARGET_NOT_FOUND"


class EvalTargetConflict(EvalStoreError):
    code = "EVAL_TARGET_VERSION_CONFLICT"

    def __init__(self, expected_hash: str, current_hash: str) -> None:
        self.expected_hash = expected_hash
        self.current_hash = current_hash
        super().__init__("logic graph target hash changed")


class EvalIntegrityError(EvalStoreError):
    code = "EVAL_EVIDENCE_INTEGRITY_ERROR"


class EvalPersistenceError(EvalStoreError):
    code = "EVAL_PERSISTENCE_FAILED"


class LogicEvalEvidenceReader:
    """Read publishable Eval evidence using the caller's open transaction."""

    @staticmethod
    def get_evidence(
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        suite_id: str,
        report_id: str,
    ) -> LogicEvalEvidence | None:
        if not org_id or not project_id or not suite_id or not report_id:
            return None
        row = conn.execute(
            """
            SELECT r.suite_id, r.report_id, r.target_type, r.target_id,
                   r.target_revision, r.target_hash, r.gate_passed,
                   r.pass_rate, s.gate_threshold AS threshold,
                   r.passed, r.failed, r.total, r.run_at,
                   gr.graph_hash AS revision_hash
            FROM aip_eval_report r
            JOIN aip_eval_suite s
              ON s.org_id=r.org_id AND s.project_id=r.project_id
             AND s.suite_id=r.suite_id
            JOIN aip_logic_graph_revision gr
              ON gr.org_id=r.org_id AND gr.project_id=r.project_id
             AND gr.graph_id=r.target_id AND gr.revision=r.target_revision
            WHERE r.org_id=%s AND r.project_id=%s
              AND r.suite_id=%s AND r.report_id=%s
            """,
            (org_id, project_id, suite_id, report_id),
        ).fetchone()
        if row is None or str(row["revision_hash"]) != str(row["target_hash"]):
            return None
        try:
            return LogicEvalEvidence(
                suite_id=str(row["suite_id"]),
                report_id=str(row["report_id"]),
                target_type=str(row["target_type"]),
                target_id=str(row["target_id"]),
                target_revision=int(row["target_revision"]),
                target_hash=str(row["target_hash"]),
                gate_passed=bool(row["gate_passed"]),
                pass_rate=float(row["pass_rate"]),
                threshold=float(row["threshold"]),
                passed=int(row["passed"]),
                failed=int(row["failed"]),
                total=int(row["total"]),
                run_at=row["run_at"],
                expires_at=None,
            )
        except (TypeError, ValueError):
            return None


class EvalEvidenceStore:
    """Stateless store; all public reads are scoped by org and project."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def create_suite(
        self, org_id: str, project_id: str, actor: str, suite: EvalSuite
    ) -> EvalSuite:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """
                    INSERT INTO aip_eval_suite (
                      org_id, project_id, suite_id, name, cases,
                      gate_threshold, actor, created_at
                    )
                    VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,NOW())
                    ON CONFLICT (org_id, project_id, suite_id) DO NOTHING
                    RETURNING suite_id, name, cases, gate_threshold
                    """,
                    (
                        org_id,
                        project_id,
                        suite.id,
                        suite.name,
                        json.dumps(
                            [case.model_dump(mode="json") for case in suite.cases],
                            ensure_ascii=False,
                        ),
                        suite.gate_threshold,
                        actor,
                    ),
                ).fetchone()
                if row is None:
                    raise EvalConflict(f"eval suite {suite.id} already exists")
                conn.commit()
        except EvalStoreError:
            raise
        except Exception as exc:
            raise EvalPersistenceError("eval suite persistence failed") from exc
        return self._suite_from_row(row)

    def list_suites(self, org_id: str, project_id: str) -> list[EvalSuite]:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    """
                    SELECT suite_id, name, cases, gate_threshold
                    FROM aip_eval_suite
                    WHERE org_id=%s AND project_id=%s
                    ORDER BY created_at DESC, suite_id ASC
                    """,
                    (org_id, project_id),
                ).fetchall()
        except Exception as exc:
            raise EvalPersistenceError("eval suite history is unavailable") from exc
        return [self._suite_from_row(row) for row in rows]

    def get_suite(self, org_id: str, project_id: str, suite_id: str) -> EvalSuite:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """
                    SELECT suite_id, name, cases, gate_threshold
                    FROM aip_eval_suite
                    WHERE org_id=%s AND project_id=%s AND suite_id=%s
                    """,
                    (org_id, project_id, suite_id),
                ).fetchone()
        except Exception as exc:
            raise EvalPersistenceError("eval suite read failed") from exc
        if row is None:
            raise EvalNotFound(f"eval suite {suite_id} not found")
        return self._suite_from_row(row)

    def require_logic_target(
        self, org_id: str, project_id: str, target: LogicGraphEvalTarget
    ) -> None:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                self._require_logic_target_with_conn(conn, org_id, project_id, target)
        except EvalStoreError:
            raise
        except Exception as exc:
            raise EvalPersistenceError("eval target verification failed") from exc

    def save_report(
        self, org_id: str, project_id: str, actor: str, report: EvalReportEvidence
    ) -> EvalReportEvidence:
        self._require_scope(org_id, project_id)
        target = LogicGraphEvalTarget.model_validate(
            report.model_dump(
                include={"target_type", "target_id", "target_revision", "target_hash"}
            )
        )
        try:
            with self._connect_factory() as conn:
                suite_row = conn.execute(
                    """
                    SELECT suite_id, name, cases, gate_threshold
                    FROM aip_eval_suite
                    WHERE org_id=%s AND project_id=%s AND suite_id=%s
                    """,
                    (org_id, project_id, report.suite_id),
                ).fetchone()
                if suite_row is None:
                    raise EvalNotFound(f"eval suite {report.suite_id} not found")
                suite = self._suite_from_row(suite_row)
                self._validate_report(report, suite)
                self._require_logic_target_with_conn(
                    conn, org_id, project_id, target
                )
                row = conn.execute(
                    """
                    INSERT INTO aip_eval_report (
                      org_id, project_id, report_id, suite_id,
                      target_type, target_id, target_revision, target_hash,
                      results, pass_rate, passed, failed, total, gate_passed,
                      run_at, actor
                    )
                    VALUES (
                      %s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,
                      %s,%s,%s,%s,%s,%s::timestamptz,%s
                    )
                    ON CONFLICT (org_id, project_id, report_id) DO NOTHING
                    RETURNING report_id, suite_id, target_type, target_id,
                              target_revision, target_hash, results, pass_rate,
                              passed, failed, total, gate_passed, run_at
                    """,
                    (
                        org_id,
                        project_id,
                        report.report_id,
                        report.suite_id,
                        report.target_type,
                        report.target_id,
                        report.target_revision,
                        report.target_hash,
                        json.dumps(
                            [result.model_dump(mode="json") for result in report.results],
                            ensure_ascii=False,
                        ),
                        report.pass_rate,
                        report.passed,
                        report.failed,
                        report.total,
                        report.gate_passed,
                        report.run_at,
                        actor,
                    ),
                ).fetchone()
                if row is None:
                    raise EvalConflict(f"eval report {report.report_id} already exists")
                conn.commit()
        except EvalStoreError:
            raise
        except Exception as exc:
            raise EvalPersistenceError("eval report persistence failed") from exc
        return self._report_from_row(row)

    def get_report(
        self, org_id: str, project_id: str, report_id: str
    ) -> EvalReportEvidence:
        self._require_scope(org_id, project_id)
        row = self._report_row(
            org_id,
            project_id,
            "report_id=%s",
            (report_id,),
        )
        if row is None:
            raise EvalNotFound(f"eval report {report_id} not found")
        return self._report_from_row(row)

    def latest_report(
        self,
        org_id: str,
        project_id: str,
        suite_id: str,
        *,
        target: LogicGraphEvalTarget | None = None,
    ) -> EvalReportEvidence:
        self._require_scope(org_id, project_id)
        if target is None:
            predicate = "suite_id=%s"
            params: tuple[Any, ...] = (suite_id,)
        else:
            predicate = (
                "suite_id=%s AND target_type=%s AND target_id=%s "
                "AND target_revision=%s AND target_hash=%s"
            )
            params = (
                suite_id,
                target.target_type,
                target.target_id,
                target.target_revision,
                target.target_hash,
            )
        row = self._report_row(
            org_id,
            project_id,
            predicate,
            params,
            order="ORDER BY run_at DESC, report_id DESC LIMIT 1",
        )
        if row is None:
            raise EvalNotFound(f"eval suite {suite_id} has no matching report")
        return self._report_from_row(row)

    def history(
        self, org_id: str, project_id: str, suite_id: str
    ) -> list[EvalReportEvidence]:
        self._require_scope(org_id, project_id)
        try:
            with self._connect_factory() as conn:
                rows = conn.execute(
                    f"""
                    {self._REPORT_SELECT}
                    WHERE org_id=%s AND project_id=%s AND suite_id=%s
                    ORDER BY run_at ASC, report_id ASC
                    """,
                    (org_id, project_id, suite_id),
                ).fetchall()
        except Exception as exc:
            raise EvalPersistenceError("eval report history is unavailable") from exc
        return [self._report_from_row(row) for row in rows]

    _REPORT_SELECT = """
        SELECT report_id, suite_id, target_type, target_id,
               target_revision, target_hash, results, pass_rate,
               passed, failed, total, gate_passed, run_at
        FROM aip_eval_report
    """

    def _report_row(
        self,
        org_id: str,
        project_id: str,
        predicate: str,
        params: tuple[Any, ...],
        *,
        order: str = "",
    ) -> Any | None:
        try:
            with self._connect_factory() as conn:
                return conn.execute(
                    f"""
                    {self._REPORT_SELECT}
                    WHERE org_id=%s AND project_id=%s AND {predicate}
                    {order}
                    """,
                    (org_id, project_id, *params),
                ).fetchone()
        except Exception as exc:
            raise EvalPersistenceError("eval report read failed") from exc

    @staticmethod
    def _require_logic_target_with_conn(
        conn: Any,
        org_id: str,
        project_id: str,
        target: LogicGraphEvalTarget,
    ) -> None:
        row = conn.execute(
            """
            SELECT graph_hash
            FROM aip_logic_graph_revision
            WHERE org_id=%s AND project_id=%s AND graph_id=%s AND revision=%s
            """,
            (org_id, project_id, target.target_id, target.target_revision),
        ).fetchone()
        if row is None:
            raise EvalTargetNotFound("logic graph revision target not found")
        current_hash = str(row["graph_hash"])
        if current_hash != target.target_hash:
            raise EvalTargetConflict(target.target_hash, current_hash)

    @staticmethod
    def _validate_report(report: EvalReportEvidence, suite: EvalSuite) -> None:
        threshold_passed = report.pass_rate >= suite.gate_threshold
        if report.gate_passed != threshold_passed:
            raise EvalIntegrityError("gate result contradicts persisted suite threshold")
        suite_case_ids = [case.id for case in suite.cases]
        result_case_ids = [result.case_id for result in report.results]
        if result_case_ids != suite_case_ids:
            raise EvalIntegrityError("report cases contradict persisted suite")

    @staticmethod
    def _suite_from_row(row: Any) -> EvalSuite:
        return EvalSuite(
            id=str(row["suite_id"]),
            name=str(row["name"]),
            cases=[TestCase.model_validate(case) for case in list(row["cases"] or [])],
            gate_threshold=float(row["gate_threshold"]),
        )

    @staticmethod
    def _report_from_row(row: Any) -> EvalReportEvidence:
        run_at = row["run_at"]
        run_at_text = run_at.isoformat() if hasattr(run_at, "isoformat") else str(run_at)
        return EvalReportEvidence(
            report_id=str(row["report_id"]),
            suite_id=str(row["suite_id"]),
            target_type=str(row["target_type"]),
            target_id=str(row["target_id"]),
            target_revision=int(row["target_revision"]),
            target_hash=str(row["target_hash"]),
            results=list(row["results"] or []),
            pass_rate=float(row["pass_rate"]),
            passed=int(row["passed"]),
            failed=int(row["failed"]),
            total=int(row["total"]),
            gate_passed=bool(row["gate_passed"]),
            run_at=run_at_text,
        )

    @staticmethod
    def _require_scope(org_id: str, project_id: str) -> None:
        if not org_id or not project_id:
            raise ValueError("org_id and project_id are required")
