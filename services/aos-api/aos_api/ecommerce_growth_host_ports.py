"""Trusted host ports for the ecommerce growth extension package."""

from __future__ import annotations

import inspect
import math
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.tenant_scope import TenantScope


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_FORBIDDEN_COMMAND_KEYS = {
    "tenant",
    "orgid",
    "projectid",
    "dispatchref",
    "handlerkind",
    "dispatchrevision",
    "installationid",
    "generation",
    "executionepoch",
    "cutovergroupid",
    "cutovergrouprevision",
    "secret",
    "secretref",
    "providerurl",
    "sql",
    "allowed",
    "authorized",
    "isallowed",
    "isauthorized",
    "sourceaccessauthorized",
    "approved",
}
ConnectFactory = Callable[[TenantScope], AbstractContextManager[Any]]


class EcommerceGrowthHostError(RuntimeError):
    """Base error that does not expose database details to a package."""


class EcommerceGrowthHostBlocked(EcommerceGrowthHostError):
    """Current installation or dispatch authority is not executable."""


class EcommerceGrowthHostConflict(EcommerceGrowthHostError):
    """An exact dispatch or Receipt reference drifted."""


class DispatchAuthorityRef(Protocol):
    org_id: str
    project_id: str
    operation_id: str
    handler_kind: str
    dispatch_revision: int
    installation_id: str | None
    generation: str | None
    execution_epoch: int | None
    cutover_group_id: str
    cutover_group_revision: int


class HostCommandExecutor(Protocol):
    def __call__(
        self,
        *,
        transaction: "HostTransaction",
        scope: TenantScope,
        dispatch_ref: DispatchAuthorityRef,
        command: Mapping[str, Any],
        checked_at: datetime,
        occurred_at: datetime | None,
    ) -> Mapping[str, Any]: ...


class HostAuthorityRevalidator(Protocol):
    def __call__(
        self,
        *,
        transaction: "HostTransaction",
        scope: TenantScope,
        dispatch: "EcommerceGrowthDispatchSnapshot",
        command: Mapping[str, Any],
    ) -> None: ...


class HostReceiptVerifier(Protocol):
    def __call__(
        self,
        *,
        transaction: "HostTransaction",
        scope: TenantScope,
        dispatch: "EcommerceGrowthDispatchSnapshot",
        command: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class EcommerceGrowthDispatchSnapshot:
    operation_id: str
    dispatch_revision: int
    installation_id: UUID
    generation: UUID
    execution_epoch: int
    cutover_group_id: UUID
    cutover_group_revision: int
    runtime_revision: int
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class EcommerceGrowthOperationBinding:
    operation_id: str
    receipt_keys: tuple[str, ...]
    authority_kinds: tuple[str, ...]
    revalidate: HostAuthorityRevalidator
    execute: HostCommandExecutor
    verify_receipt: HostReceiptVerifier

    def __post_init__(self) -> None:
        if (
            type(self.operation_id) is not str
            or not self.operation_id
            or not self.receipt_keys
            or len(set(self.receipt_keys)) != len(self.receipt_keys)
            or any(type(key) is not str or not key for key in self.receipt_keys)
            or not self.authority_kinds
            or len(set(self.authority_kinds)) != len(self.authority_kinds)
            or any(type(kind) is not str or not kind for kind in self.authority_kinds)
            or not callable(self.revalidate)
            or not callable(self.execute)
            or not callable(self.verify_receipt)
        ):
            raise ValueError("operation binding must define exact trusted host contracts")


class HostTransaction:
    """Narrow transaction view; domain executors cannot commit independently."""

    __slots__ = ("__connection",)

    def __init__(self, connection: Any) -> None:
        self.__connection = connection

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        if type(query) is not str or not query.strip():
            raise TypeError("host transaction query is required")
        return self.__connection.execute(query, params)

    def run_current_source_snapshot(self, owner, *, scope, ref, actor, execute):
        """Trusted source Owner uses this same connection without exposing it."""
        from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
        if type(owner) is not PipelineSourceSelectionOwner:
            raise TypeError('exact current source Owner required')
        return owner.run_current_snapshot(self.__connection, scope=scope, ref=ref,
            actor=actor, execute=execute)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _reject_authority_overrides(value: Any, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("command depth exceeded")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("command keys must be strings")
        if any(_normalized_key(key) in _FORBIDDEN_COMMAND_KEYS for key in value):
            raise ValueError("command cannot override host authority")
        for child in value.values():
            _reject_authority_overrides(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _reject_authority_overrides(child, depth + 1)
    elif type(value) is float and not math.isfinite(value):
        raise ValueError("command numbers must be finite")
    elif value is not None and type(value) not in {str, int, float, bool}:
        raise ValueError("command must be a strict JSON-compatible tree")


def _strict_receipt(result: Any, receipt_keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise EcommerceGrowthHostConflict("host executor must return a Receipt mapping")
    payload = deepcopy(dict(result))
    refs = [payload.get(key) for key in receipt_keys if payload.get(key) is not None]
    if len(refs) != 1:
        raise EcommerceGrowthHostConflict("host executor must return one target Receipt ref")
    ref = refs[0]
    if (
        type(ref) is not dict
        or set(ref) - {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
        or not {"resourceType", "resourceId", "revision", "contentHash"} <= set(ref)
        or type(ref["resourceType"]) is not str
        or not ref["resourceType"].strip()
        or type(ref["resourceId"]) is not str
        or not ref["resourceId"].strip()
        or type(ref["revision"]) is not int
        or ref["revision"] <= 0
        or type(ref["contentHash"]) is not str
        or not _SHA256.fullmatch(ref["contentHash"])
        or ("receiptId" in ref and (type(ref["receiptId"]) is not str or not ref["receiptId"].strip()))
    ):
        raise EcommerceGrowthHostConflict("host executor returned an invalid exact Receipt ref")
    return payload


class LockedEcommerceGrowthHostPort:
    """Revalidate the full dispatch group and execute inside one transaction."""

    def __init__(
        self,
        bindings: Mapping[str, EcommerceGrowthOperationBinding],
        *,
        connect_factory: ConnectFactory = connect_serializable,
    ) -> None:
        if (
            not bindings
            or any(
                type(key) is not str
                or not isinstance(value, EcommerceGrowthOperationBinding)
                or value.operation_id != key
                for key, value in bindings.items()
            )
        ):
            raise ValueError("one or more exact trusted operation bindings are required")
        self._bindings = dict(bindings)
        self._connect_factory = connect_factory

    def commit(
        self,
        *,
        dispatch_ref: DispatchAuthorityRef,
        command: Mapping[str, Any],
        occurred_at: datetime | None = None,
    ) -> Mapping[str, Any]:
        binding = self._bindings.get(getattr(dispatch_ref, "operation_id", None))
        if binding is None:
            raise EcommerceGrowthHostBlocked("dispatch operation has no trusted host executor")
        if occurred_at is not None and occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must include timezone")
        if type(command) is not dict:
            raise TypeError("command must be a strict mapping")
        _reject_authority_overrides(command)
        scope = TenantScope(dispatch_ref.org_id, dispatch_ref.project_id)
        try:
            with self._connect_factory(scope) as conn:
                snapshot = self._lock_and_revalidate(conn, scope, dispatch_ref)
                transaction = HostTransaction(conn)
                validation = binding.revalidate(
                    transaction=transaction,
                    scope=scope,
                    dispatch=snapshot,
                    command=deepcopy(command),
                )
                if validation is not None or inspect.isawaitable(validation):
                    if inspect.iscoroutine(validation):
                        validation.close()
                    raise EcommerceGrowthHostConflict("authority revalidation must finish in the transaction")
                result = binding.execute(
                    transaction=transaction,
                    scope=scope,
                    dispatch_ref=dispatch_ref,
                    command=deepcopy(command),
                    checked_at=snapshot.checked_at,
                    occurred_at=occurred_at,
                )
                if inspect.isawaitable(result) or inspect.isgenerator(result) or inspect.isasyncgen(result):
                    if inspect.iscoroutine(result) or inspect.isgenerator(result):
                        result.close()
                    raise EcommerceGrowthHostConflict("host executor must finish inside the locked transaction")
                payload = _strict_receipt(result, binding.receipt_keys)
                persisted = binding.verify_receipt(
                    transaction=transaction,
                    scope=scope,
                    dispatch=snapshot,
                    command=deepcopy(command),
                    receipt=deepcopy(payload),
                )
                if inspect.isawaitable(persisted) or not isinstance(persisted, Mapping):
                    if inspect.iscoroutine(persisted):
                        persisted.close()
                    raise EcommerceGrowthHostConflict("target Receipt must be read back in the transaction")
                if deepcopy(dict(persisted)) != payload:
                    raise EcommerceGrowthHostConflict("target Receipt readback drifted")
                conn.commit()
                return payload
        except (EcommerceGrowthHostError, TypeError, ValueError):
            raise
        except Exception as exc:
            raise EcommerceGrowthHostError("ecommerce growth host transaction failed") from exc

    @staticmethod
    def _lock_and_revalidate(
        conn: Any,
        scope: TenantScope,
        dispatch_ref: DispatchAuthorityRef,
    ) -> EcommerceGrowthDispatchSnapshot:
        if dispatch_ref.handler_kind != "extension":
            raise EcommerceGrowthHostBlocked("legacy dispatch cannot enter the extension host")
        try:
            installation_id = UUID(str(dispatch_ref.installation_id))
            generation = UUID(str(dispatch_ref.generation))
            group_id = UUID(str(dispatch_ref.cutover_group_id))
        except (TypeError, ValueError, AttributeError) as exc:
            raise EcommerceGrowthHostConflict("dispatch runtime identity is invalid") from exc
        if type(dispatch_ref.execution_epoch) is not int or dispatch_ref.execution_epoch <= 0:
            raise EcommerceGrowthHostConflict("dispatch execution epoch is invalid")
        group_rows = conn.execute(
            "SELECT * FROM public.extension_dispatch_lock_group_a0v_028(%s)",
            (group_id,),
        ).fetchall()
        target = next(
            (row for row in group_rows if row["operation_id"] == dispatch_ref.operation_id),
            None,
        )
        if target is None:
            raise EcommerceGrowthHostBlocked("current dispatch authority is unavailable")
        expected = (
            "extension",
            installation_id,
            generation,
            dispatch_ref.execution_epoch,
            False,
            dispatch_ref.dispatch_revision,
            group_id,
            dispatch_ref.cutover_group_revision,
        )
        actual = tuple(
            target[key]
            for key in (
                "handler_kind",
                "installation_id",
                "generation",
                "execution_epoch",
                "operation_fence",
                "revision",
                "cutover_group_id",
                "cutover_group_revision",
            )
        )
        if actual != expected:
            raise EcommerceGrowthHostConflict("exact dispatch authority drifted")
        if any(
            row["handler_kind"] != "extension"
            or row["cutover_group_revision"] != dispatch_ref.cutover_group_revision
            or row["operation_fence"] is not False
            or row["installation_id"] is None
            or row["generation"] is None
            or type(row["execution_epoch"]) is not int
            or row["execution_epoch"] <= 0
            for row in group_rows
        ):
            raise EcommerceGrowthHostBlocked("cutover group is not executable")
        runtime_rows: dict[tuple[UUID, UUID], Mapping[str, Any]] = {}
        for binding_key in sorted(
            {(row["installation_id"], row["generation"]) for row in group_rows},
            key=lambda item: (str(item[0]), str(item[1])),
        ):
            runtime = conn.execute(
                """SELECT installation_id,generation,execution_epoch,revision,
                          desired_state,observed_state,enabled,operation_fence
                     FROM extension_runtime_binding
                    WHERE org_id=%s AND project_id=%s
                      AND installation_id=%s AND generation=%s
                    FOR UPDATE""",
                (*scope.key, *binding_key),
            ).fetchone()
            if runtime is None:
                raise EcommerceGrowthHostBlocked("runtime binding is unavailable")
            runtime_rows[binding_key] = runtime
        if any(
            runtime_rows[(row["installation_id"], row["generation"])]["execution_epoch"]
            != row["execution_epoch"]
            or runtime_rows[(row["installation_id"], row["generation"])]["desired_state"] != "enabled"
            or runtime_rows[(row["installation_id"], row["generation"])]["observed_state"] != "ready"
            or runtime_rows[(row["installation_id"], row["generation"])]["enabled"] is not True
            or runtime_rows[(row["installation_id"], row["generation"])]["operation_fence"] is not False
            for row in group_rows
        ):
            raise EcommerceGrowthHostBlocked("runtime binding is not executable")
        target_runtime = runtime_rows[(installation_id, generation)]
        checked_at = conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()["checked_at"]
        return EcommerceGrowthDispatchSnapshot(
            operation_id=target["operation_id"],
            dispatch_revision=target["revision"],
            installation_id=target["installation_id"],
            generation=target["generation"],
            execution_epoch=target["execution_epoch"],
            cutover_group_id=target["cutover_group_id"],
            cutover_group_revision=target["cutover_group_revision"],
            runtime_revision=target_runtime["revision"],
            checked_at=checked_at,
        )


__all__ = [
    "DispatchAuthorityRef",
    "EcommerceGrowthDispatchSnapshot",
    "EcommerceGrowthHostBlocked",
    "EcommerceGrowthHostConflict",
    "EcommerceGrowthHostError",
    "EcommerceGrowthOperationBinding",
    "HostAuthorityRevalidator",
    "HostCommandExecutor",
    "HostReceiptVerifier",
    "HostTransaction",
    "LockedEcommerceGrowthHostPort",
    "ConnectFactory",
]
