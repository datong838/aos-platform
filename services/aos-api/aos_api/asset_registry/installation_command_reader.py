"""Strict read-only recovery of an existing installation command receipt.

Missing records never execute a command. ``replayed`` retains the original
receipt cache-hit meaning; this reader does not replay a handler or Run.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection
import inspect
import re
from typing import Any

import psycopg

from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.contracts import SHA256_PATTERN
from aos_api.asset_registry.errors import IdempotencyConflictError, LockIntegrityCorruptError
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import (
    CommandReceipt,
    ConnectFactory,
    InstallationPersistenceError,
    PostgresInstallationStore,
    _idempotency_key,
    _normalized_text,
    _receipt_from_row,
)
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import ORG_GUC, PROJECT_GUC, TenantScope

_ORIGINAL_AUTHORIZE_RECEIPT = InstallationService._authorize_receipt


class ReadOnlyInstallationCommandReader:
    """Use explicit original read-only stores and original receipt authorization."""

    def __init__(
        self, *, connect_factory: ConnectFactory, installation_service: InstallationService
    ) -> None:
        if not callable(connect_factory):
            raise ValueError("explicit read-only connection factory required")
        self._connect_factory = connect_factory
        self._service = installation_service
        self._assert_binding()

    def _assert_binding(self) -> None:
        service = self._service
        if (
            type(service) is not InstallationService
            or type(service._store) is not PostgresInstallationStore
            or type(service._composition_store) is not PostgresCompositionStore
            or service._store._connect_factory is not self._connect_factory
            or service._composition_store._connect_factory is not self._connect_factory
            or getattr(service._authorize_receipt, "__func__", None)
            is not _ORIGINAL_AUTHORIZE_RECEIPT
        ):
            raise ValueError("original read-only service/store authorization binding required")

    @staticmethod
    def _require_read_only(conn: Any) -> None:
        mode = conn.execute("SHOW transaction_read_only").fetchone()
        if mode is None or mode["transaction_read_only"] != "on":
            raise PermissionError("receipt lookup requires an active READ ONLY transaction")

    @staticmethod
    def _require_scope(conn: Any, scope: TenantScope) -> None:
        row = conn.execute(
            "SELECT current_setting(%s, true) AS org_id, current_setting(%s, true) AS project_id",
            (ORG_GUC, PROJECT_GUC),
        ).fetchone()
        if row is None or (row["org_id"], row["project_id"]) != scope.key:
            raise PermissionError("receipt transaction tenant scope changed")

    @staticmethod
    def _check_current(conn: Any, check: Callable[[Any], bool]) -> None:
        verdict = check(conn)
        if inspect.isawaitable(verdict) or inspect.isgenerator(verdict) or inspect.isasyncgen(verdict):
            if isinstance(verdict, asyncio.Future):
                verdict.cancel()
            if inspect.iscoroutine(verdict) or inspect.isgenerator(verdict):
                verdict.close()
            # Do not drive an async generator merely to clean it up: its code
            # belongs to the rejected asynchronous guard, not this reader.
            raise PermissionError("current receipt check must finish synchronously")
        if verdict is not True:
            raise PermissionError("current receipt access denied")

    def read(
        self,
        *,
        org_id: str,
        project_id: str,
        operation: str,
        idempotency_key: str,
        subject: str,
        request_hash: str,
        markings: Collection[str],
        current_check: Callable[[Any], bool],
    ) -> CommandReceipt | None:
        self._assert_binding()
        org_id = _normalized_text(org_id, "org_id")
        project_id = _normalized_text(project_id, "project_id")
        scope = TenantScope(org_id, project_id)
        operation = _normalized_text(operation, "operation")
        idempotency_key = _idempotency_key(idempotency_key)
        subject = _normalized_text(subject, "subject")
        if not isinstance(request_hash, str) or re.fullmatch(SHA256_PATTERN, request_hash) is None:
            raise ValueError("request_hash must be a canonical SHA-256 value")
        if (
            not callable(current_check)
            or inspect.iscoroutinefunction(current_check)
            or inspect.isgeneratorfunction(current_check)
            or inspect.isasyncgenfunction(current_check)
        ):
            raise ValueError("explicit synchronous current receipt check required")
        try:
            with self._connect_factory() as conn:
                self._require_read_only(conn)
                apply_asset_transaction_scope(conn, org_id=org_id, project_id=project_id)
                self._check_current(conn, current_check)
                self._assert_binding()
                self._require_read_only(conn)
                self._require_scope(conn, scope)
                row = conn.execute(
                    """
                    SELECT subject, request_hash, status_code, response_json, response_etag
                      FROM bundle_installation_command
                     WHERE org_id = %s AND project_id = %s
                       AND operation = %s AND idempotency_key = %s
                    """,
                    (org_id, project_id, operation, idempotency_key),
                ).fetchone()
                if row is None:
                    return None
                if row["request_hash"] != request_hash:
                    raise IdempotencyConflictError("idempotency key was used for a different request")
                if row["subject"] != subject:
                    raise LockIntegrityCorruptError()
                receipt = _receipt_from_row(row, replayed=True)
                self._assert_binding()
                self._service._authorize_receipt(
                    receipt, org_id=org_id, project_id=project_id, markings=markings
                )
                return receipt
        except psycopg.Error as exc:
            raise InstallationPersistenceError() from exc
