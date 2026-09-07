"""Typed connector request envelope without credentials or arbitrary targets."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Any, Mapping, Protocol, TypeVar

from .dispatch import DispatchRef


_OPERATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}")
_FORBIDDEN_KEYS = {
    "sql", "url", "uri", "host", "port", "password", "secret", "token", "cookie",
    "authorization", "headers", "orgid", "projectid", "tenant", "connectionstring",
}
_T = TypeVar("_T")


def _safe_parameters(value: Any, depth: int = 0) -> None:
    if depth > 32:
        raise ValueError("connector parameters are too deep")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str) or key.replace("_", "").lower() in _FORBIDDEN_KEYS:
                raise ValueError("connector parameters contain a forbidden key")
            _safe_parameters(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _safe_parameters(child, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("connector parameters must contain finite numbers")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise ValueError("connector parameters must be JSON values")


@dataclass(frozen=True, slots=True)
class ConnectorRequest:
    connection_ref: Mapping[str, Any]
    operation_id: str
    typed_params: Mapping[str, Any]
    cutoff_at: datetime
    idempotency_key: str

    def __post_init__(self) -> None:
        if not _OPERATION_ID.fullmatch(self.operation_id):
            raise ValueError("invalid connector operation id")
        if self.cutoff_at.utcoffset() is None:
            raise ValueError("connector cutoff must include timezone")
        if not 1 <= len(self.idempotency_key.strip()) <= 200:
            raise ValueError("invalid connector idempotency key")
        if set(self.connection_ref) != {"resourceType", "resourceId", "revision", "contentHash"}:
            raise ValueError("connector connectionRef must be exact")
        if self.connection_ref["resourceType"] != "ConnectionRevision":
            raise ValueError("connector requires ConnectionRevision")
        if (
            type(self.connection_ref["resourceId"]) is not str
            or not 1 <= len(self.connection_ref["resourceId"].strip()) <= 240
            or type(self.connection_ref["revision"]) is not int
            or self.connection_ref["revision"] <= 0
            or type(self.connection_ref["contentHash"]) is not str
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.connection_ref["contentHash"])
        ):
            raise ValueError("connector requires an exact ConnectionRevision")
        _safe_parameters(self.typed_params)

    def to_payload(self) -> dict[str, Any]:
        return {
            "connectionRef": deepcopy(dict(self.connection_ref)),
            "operationId": self.operation_id,
            "typedParams": deepcopy(dict(self.typed_params)),
            "cutoffAt": self.cutoff_at.isoformat(),
            "idempotencyKey": self.idempotency_key,
        }


class ConnectorPort(Protocol):
    def request(self, *, dispatch_ref: DispatchRef, request: ConnectorRequest) -> _T: ...


def request_connector(port: ConnectorPort, dispatch_ref: DispatchRef, request: ConnectorRequest) -> _T:
    if dispatch_ref.handler_kind != "extension" or dispatch_ref.operation_id != request.operation_id:
        raise PermissionError("connector dispatch does not authorize this operation")
    return port.request(dispatch_ref=dispatch_ref, request=request)


__all__ = ["ConnectorPort", "ConnectorRequest", "request_connector"]
