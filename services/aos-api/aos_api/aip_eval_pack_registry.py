"""Tenant-scoped AIP-4 E1A EvalPack registry."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityConflict,
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
    AipEvalAuthorityStore,
)
from aos_api.aip_eval_contracts import (
    DatasetRevisionRef,
    EvalDatasetManifest,
    EvalSuiteRevision,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


def compute_eval_suite_hash(suite: EvalSuiteRevision) -> str:
    payload = suite.model_dump(mode="json", by_alias=True, exclude={"content_hash"})
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AipEvalPackRegistry:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._authority = AipEvalAuthorityStore(connect_factory=self._connect_factory)

    def register_dataset_revision(
        self,
        scope: TenantScope,
        ref: DatasetRevisionRef,
        manifest: EvalDatasetManifest,
        *,
        actor: str,
    ) -> DatasetRevisionRef:
        if ref.source_hash != manifest.source_hash:
            raise ValueError("dataset source hash does not match its manifest")
        return self._authority.create_dataset_revision(
            scope,
            ref,
            manifest=manifest.model_dump(mode="json", by_alias=True),
            actor=actor,
        )

    def register_suite_revision(
        self, scope: TenantScope, suite: EvalSuiteRevision, *, actor: str
    ) -> EvalSuiteRevision:
        if not actor.strip():
            raise ValueError("actor is required")
        expected_hash = compute_eval_suite_hash(suite)
        if suite.content_hash != expected_hash:
            raise ValueError("eval suite content hash is not canonical")
        try:
            dataset = self._authority.get_dataset_revision(
                scope, suite.dataset.dataset_id, suite.dataset.revision
            )
            if dataset != suite.dataset:
                raise AipEvalAuthorityConflict("eval suite dataset reference drifted")
            with self._connect(scope) as conn:
                row = conn.execute(
                    """INSERT INTO aip_eval_suite_revision (
                       org_id,project_id,suite_id,revision,content_hash,target_ref,
                       dataset_ref,judge_ref,cases,gate_threshold,actor,created_at
                       ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                                 %s::jsonb,%s,%s,NOW())
                       ON CONFLICT (org_id,project_id,suite_id,revision) DO NOTHING
                       RETURNING *""",
                    (
                        scope.org_id,
                        scope.project_id,
                        suite.suite_id,
                        suite.revision,
                        suite.content_hash,
                        self._json(suite.target),
                        self._json(suite.dataset),
                        self._json(suite.judge),
                        self._json(suite.cases),
                        suite.gate_threshold,
                        actor.strip(),
                    ),
                ).fetchone()
                if row is None:
                    row = self._suite_row(
                        conn, scope, suite.suite_id, suite.revision
                    )
                    if row is None or self._suite_from_row(row) != suite:
                        raise AipEvalAuthorityConflict(
                            "eval suite revision already exists with different content"
                        )
                conn.commit()
                return self._suite_from_row(row)
        except (AipEvalAuthorityConflict, AipEvalAuthorityNotFound):
            raise
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "eval suite revision persistence failed"
            ) from exc

    def get_suite_revision(
        self, scope: TenantScope, suite_id: str, revision: int
    ) -> EvalSuiteRevision:
        try:
            with self._connect(scope) as conn:
                row = self._suite_row(conn, scope, suite_id, revision)
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "eval suite revision read failed"
            ) from exc
        if row is None:
            raise AipEvalAuthorityNotFound("eval suite revision not found")
        return self._suite_from_row(row)

    def list_suite_revisions(
        self, scope: TenantScope, *, suite_id: str | None = None
    ) -> list[EvalSuiteRevision]:
        try:
            with self._connect(scope) as conn:
                if suite_id is None:
                    rows = conn.execute(
                        """SELECT * FROM aip_eval_suite_revision
                           WHERE org_id=%s AND project_id=%s
                           ORDER BY suite_id,revision""",
                        (scope.org_id, scope.project_id),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT * FROM aip_eval_suite_revision
                           WHERE org_id=%s AND project_id=%s AND suite_id=%s
                           ORDER BY revision""",
                        (scope.org_id, scope.project_id, suite_id),
                    ).fetchall()
        except Exception as exc:
            raise AipEvalAuthorityPersistenceError(
                "eval suite revision list failed"
            ) from exc
        return [self._suite_from_row(row) for row in rows]

    def _connect(self, scope: TenantScope) -> AbstractContextManager[Any]:
        if self._connect_factory is db_connect:
            return db_connect(scope)
        try:
            return self._connect_factory(scope)
        except TypeError:
            return self._connect_factory()

    @staticmethod
    def _suite_row(conn: Any, scope: TenantScope, suite_id: str, revision: int):
        return conn.execute(
            """SELECT * FROM aip_eval_suite_revision
               WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
            (scope.org_id, scope.project_id, suite_id, revision),
        ).fetchone()

    @staticmethod
    def _suite_from_row(row: Any) -> EvalSuiteRevision:
        return EvalSuiteRevision(
            suite_id=row["suite_id"],
            revision=row["revision"],
            content_hash=row["content_hash"],
            target=row["target_ref"],
            dataset=row["dataset_ref"],
            judge=row["judge_ref"],
            cases=row["cases"],
            gate_threshold=row["gate_threshold"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        elif isinstance(value, list):
            value = [
                item.model_dump(mode="json", by_alias=True)
                if hasattr(item, "model_dump")
                else item
                for item in value
            ]
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = ["AipEvalPackRegistry", "compute_eval_suite_hash"]
