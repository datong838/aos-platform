"""Generic host-owned validation broker for extension connector requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import TYPE_CHECKING, Any, Literal, Mapping, Protocol

if TYPE_CHECKING:
    from aos_extension_sdk import ConnectorRequest, DispatchRef


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_REF_FIELDS = {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
_OPERATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}")
_DYNAMIC_TARGET_NAMES = {
    "database", "databasename", "query", "querytarget", "schema", "schemaname", "table",
    "tablename",
}


@dataclass(frozen=True, slots=True)
class ParameterRule:
    name: str
    kind: Literal["integer", "string_list", "exact_ref"]
    required: bool = True
    minimum: int = 0
    maximum: int = 0
    resource_type: str | None = None
    receipt_required: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.name) is not str
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]{0,79}", self.name)
            or re.sub(r"[^A-Za-z0-9]", "", self.name).casefold() in _DYNAMIC_TARGET_NAMES
            or self.kind not in {"integer", "string_list", "exact_ref"}
            or type(self.required) is not bool
            or type(self.minimum) is not int
            or type(self.maximum) is not int
            or not 0 <= self.minimum <= self.maximum <= 1000
            or type(self.receipt_required) is not bool
        ):
            raise ValueError("invalid connector parameter rule")
        if self.kind == "exact_ref" and not self.resource_type:
            raise ValueError("exact-ref rule requires a resource type")
        if self.kind != "exact_ref" and (
            self.resource_type is not None or self.receipt_required
        ):
            raise ValueError("only exact-ref rules may declare reference constraints")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ParameterRule":
        allowed = {
            "name", "kind", "required", "minimum", "maximum", "resourceType",
            "receiptRequired",
        }
        if not isinstance(payload, Mapping) or set(payload) - allowed or not {"name", "kind"} <= set(payload):
            raise ValueError("invalid connector parameter declaration")
        return cls(
            name=payload["name"],
            kind=payload["kind"],
            required=payload.get("required", True),
            minimum=payload.get("minimum", 0),
            maximum=payload.get("maximum", 0),
            resource_type=payload.get("resourceType"),
            receipt_required=payload.get("receiptRequired", False),
        )


@dataclass(frozen=True, slots=True)
class ConnectorOperationSchema:
    operation_id: str
    parameters: tuple[ParameterRule, ...]

    def __post_init__(self) -> None:
        names = [item.name for item in self.parameters]
        if (
            type(self.operation_id) is not str
            or not _OPERATION_ID.fullmatch(self.operation_id)
            or len(names) != len(set(names))
        ):
            raise ValueError("connector operation schema must be exact")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ConnectorOperationSchema":
        if not isinstance(payload, Mapping) or set(payload) != {"operationId", "parameters"}:
            raise ValueError("invalid connector operation declaration")
        parameters = payload["parameters"]
        if not isinstance(parameters, list) or not 1 <= len(parameters) <= 64:
            raise ValueError("invalid connector operation parameters")
        return cls(
            operation_id=payload["operationId"],
            parameters=tuple(ParameterRule.from_payload(item) for item in parameters),
        )

    def validate(self, values: Mapping[str, Any]) -> None:
        rules = {item.name: item for item in self.parameters}
        required = {name for name, rule in rules.items() if rule.required}
        if set(values) - set(rules) or not required <= set(values):
            raise ValueError("connector parameters do not match the operation allowlist")
        for name, value in values.items():
            rule = rules[name]
            if rule.kind == "integer":
                if type(value) is not int or not rule.minimum <= value <= rule.maximum:
                    raise ValueError(f"invalid connector parameter: {name}")
            elif rule.kind == "string_list":
                if not isinstance(value, (list, tuple)) or not rule.minimum <= len(value) <= rule.maximum:
                    raise ValueError(f"invalid connector parameter: {name}")
                if any(type(item) is not str or not item.strip() for item in value):
                    raise ValueError(f"invalid connector parameter: {name}")
            else:
                _validate_exact_ref(value, rule.resource_type or "", rule.receipt_required)


def _validate_exact_ref(value: Any, resource_type: str, receipt_required: bool) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("connector authority reference must be an object")
    required = _REF_FIELDS - {"receiptId"}
    if set(value) - _REF_FIELDS or not required <= set(value):
        raise ValueError("connector authority reference must be exact")
    if (
        value["resourceType"] != resource_type
        or type(value["resourceId"]) is not str
        or not value["resourceId"].strip()
        or type(value["revision"]) is not int
        or value["revision"] <= 0
        or type(value["contentHash"]) is not str
        or not _SHA256.fullmatch(value["contentHash"])
        or (receipt_required and not value.get("receiptId"))
        or (
            "receiptId" in value
            and (
                type(value["receiptId"]) is not str
                or not 1 <= len(value["receiptId"].strip()) <= 240
            )
        )
    ):
        raise ValueError("connector authority reference drifted")


@dataclass(frozen=True, slots=True)
class ConnectorAuthoritySnapshot:
    available: bool
    connection_ref: Mapping[str, Any]
    requirement_ref: Mapping[str, Any]
    source_readiness_ref: Mapping[str, Any]
    mapping_ref: Mapping[str, Any]
    cutoff_at: datetime


class ConnectorAuthorityPort(Protocol):
    def revalidate(
        self, *, dispatch_ref: DispatchRef, request: ConnectorRequest
    ) -> ConnectorAuthoritySnapshot: ...


class ConnectorExecutorPort(Protocol):
    def execute(self, *, dispatch_ref: DispatchRef, request: ConnectorRequest) -> Mapping[str, Any]: ...


class ConnectorBroker:
    """Validate signed schema and current authority before any connector execution."""

    def __init__(
        self,
        schemas: Mapping[str, ConnectorOperationSchema],
        authority: ConnectorAuthorityPort,
        executor: ConnectorExecutorPort,
    ) -> None:
        self._schemas = dict(schemas)
        self._authority = authority
        self._executor = executor

    def request(
        self, *, dispatch_ref: DispatchRef, request: ConnectorRequest
    ) -> Mapping[str, Any]:
        if dispatch_ref.handler_kind != "extension" or dispatch_ref.operation_id != request.operation_id:
            raise PermissionError("dispatch does not authorize this connector request")
        schema = self._schemas.get(request.operation_id)
        if schema is None or schema.operation_id != request.operation_id:
            raise PermissionError("connector operation has no admitted schema")
        request.to_payload()
        schema.validate(request.typed_params)
        snapshot = self._authority.revalidate(dispatch_ref=dispatch_ref, request=request)
        params = request.typed_params
        expected = (
            (snapshot.connection_ref, request.connection_ref),
            (snapshot.requirement_ref, params["requirementRef"]),
            (snapshot.source_readiness_ref, params["sourceReadinessRef"]),
            (snapshot.mapping_ref, params["mappingRef"]),
        )
        if (
            not snapshot.available
            or snapshot.cutoff_at != request.cutoff_at
            or any(dict(actual) != dict(wanted) for actual, wanted in expected)
        ):
            raise PermissionError("connector authority is unavailable or drifted")
        result = self._executor.execute(dispatch_ref=dispatch_ref, request=request)
        if not isinstance(result, Mapping):
            raise ValueError("connector executor returned an invalid result")
        return result


__all__ = [
    "ConnectorAuthorityPort", "ConnectorAuthoritySnapshot", "ConnectorBroker",
    "ConnectorExecutorPort", "ConnectorOperationSchema", "ParameterRule",
]
