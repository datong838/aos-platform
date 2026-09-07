"""Immutable dispatch authority passed from the platform to extension ports."""

from __future__ import annotations

from copy import deepcopy
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, TypeVar
from uuid import UUID


_FIELDS = {
    "orgId",
    "projectId",
    "operationId",
    "handlerKind",
    "dispatchRevision",
    "installationId",
    "generation",
    "executionEpoch",
    "cutoverGroupId",
    "cutoverGroupRevision",
}
_OPERATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}")
_AUTHORITY_FIELDS = _FIELDS | {
    "dispatchRef",
    "org_id",
    "project_id",
    "operation_id",
    "handler_kind",
    "dispatch_revision",
    "installation_id",
    "execution_epoch",
    "cutover_group_id",
    "cutover_group_revision",
}
_T = TypeVar("_T")


def _identifier(value: Any, name: str, maximum: int = 160) -> str:
    if type(value) is not str or not 0 < len(value) <= maximum or value.strip() != value:
        raise ValueError(f"invalid {name}")
    return value


def _positive(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"invalid {name}")
    return value


def _uuid(value: Any, name: str) -> str:
    value = _identifier(value, name, 36)
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"invalid {name}") from exc
    if str(parsed) != value:
        raise ValueError(f"invalid {name}")
    return value


def _reject_authority_overrides(value: Any, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("command depth exceeded")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("command keys must be strings")
        if _AUTHORITY_FIELDS.intersection(value):
            raise ValueError("command cannot override dispatch authority")
        for child in value.values():
            _reject_authority_overrides(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _reject_authority_overrides(child, depth + 1)


@dataclass(frozen=True, slots=True)
class DispatchRef:
    """Exact dispatch head; write ports must revalidate it in their commit transaction."""

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

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DispatchRef":
        if type(payload) is not dict or set(payload) != _FIELDS:
            raise ValueError("invalid dispatch reference fields")
        handler_kind = payload["handlerKind"]
        if handler_kind not in {"legacy", "extension"}:
            raise ValueError("invalid dispatch handler")
        operation_id = _identifier(payload["operationId"], "operationId")
        if not _OPERATION_ID.fullmatch(operation_id):
            raise ValueError("invalid operationId")
        if handler_kind == "legacy":
            if any(payload[field] is not None for field in ("installationId", "generation", "executionEpoch")):
                raise ValueError("legacy dispatch cannot claim a runtime binding")
            installation_id = generation = execution_epoch = None
        else:
            installation_id = _uuid(payload["installationId"], "installationId")
            generation = _uuid(payload["generation"], "generation")
            execution_epoch = _positive(payload["executionEpoch"], "executionEpoch")
        return cls(
            org_id=_identifier(payload["orgId"], "orgId", 120),
            project_id=_identifier(payload["projectId"], "projectId", 120),
            operation_id=operation_id,
            handler_kind=handler_kind,
            dispatch_revision=_positive(payload["dispatchRevision"], "dispatchRevision"),
            installation_id=installation_id,
            generation=generation,
            execution_epoch=execution_epoch,
            cutover_group_id=_uuid(payload["cutoverGroupId"], "cutoverGroupId"),
            cutover_group_revision=_positive(
                payload["cutoverGroupRevision"], "cutoverGroupRevision"
            ),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "orgId": self.org_id,
            "projectId": self.project_id,
            "operationId": self.operation_id,
            "handlerKind": self.handler_kind,
            "dispatchRevision": self.dispatch_revision,
            "installationId": self.installation_id,
            "generation": self.generation,
            "executionEpoch": self.execution_epoch,
            "cutoverGroupId": self.cutover_group_id,
            "cutoverGroupRevision": self.cutover_group_revision,
        }


class DispatchWritePort(Protocol):
    """Host port that re-locks dispatch/runtime authority and commits atomically."""

    def commit(self, *, dispatch_ref: DispatchRef, command: Mapping[str, Any]) -> _T:
        """Revalidate the exact ref and commit, or reject without a business write."""


def commit_with_dispatch(
    port: DispatchWritePort, dispatch_ref: DispatchRef, command: Mapping[str, Any]
) -> _T:
    """Forward an immutable ref without accepting tenant or authority overrides."""
    if not isinstance(dispatch_ref, DispatchRef) or type(command) is not dict:
        raise TypeError("dispatch reference and command are required")
    _reject_authority_overrides(command)
    return port.commit(dispatch_ref=dispatch_ref, command=deepcopy(command))
