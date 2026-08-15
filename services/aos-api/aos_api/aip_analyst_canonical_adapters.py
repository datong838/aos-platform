"""P8-3B canonical read adapters for Analyst queries."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
import json
from typing import Any

from aos_api.aip_analyst_contracts import (
    AnalystQueryStatus,
    KnowledgeQueryRequest,
    QueryColumn,
    QueryFilter,
    QueryRow,
    QuerySort,
    QuerySourceRef,
    SemanticQueryRequest,
)
from aos_api.aip_analyst_query import AdapterResult, CanonicalAdapterBlocked
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_memory_contracts import KnowledgeSearch
from aos_api.aip_memory_search import AipMemoryKnowledgeSearch
from aos_api.auth import Principal
from aos_api.db import connect as db_connect
from aos_api.marking import apply_field_redaction, can_access_object, effective_markings
from aos_api.ontology_compose import assert_object_type_visible
from aos_api.ontology_object_redaction import redact_ecommerce_pii
from aos_api.tenant_scope import TenantScope


MAX_SEMANTIC_SOURCE_ROWS = 10_000
_RESERVED_FIELDS = {"id", "type"}


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return sha256(encoded).hexdigest()


def _property_name(value: dict[str, Any]) -> str | None:
    for key in ("name", "key", "id"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _value_type(value: dict[str, Any]) -> str:
    raw = str(value.get("type") or value.get("datatype") or "string").lower()
    if raw in {"int", "integer", "float", "double", "decimal", "number"}:
        return "number"
    if raw in {"bool", "boolean"}:
        return "boolean"
    if raw in {"date", "datetime", "timestamp", "timestamptz"}:
        return "datetime"
    if raw in {"object_ref", "objectref", "reference"}:
        return "object_ref"
    return "string"


def _matches(value: Any, query_filter: QueryFilter) -> bool:
    expected = query_filter.value
    try:
        if query_filter.operator == "eq":
            return value == expected
        if query_filter.operator == "neq":
            return value != expected
        if query_filter.operator == "lt":
            return value < expected
        if query_filter.operator == "lte":
            return value <= expected
        if query_filter.operator == "gt":
            return value > expected
        if query_filter.operator == "gte":
            return value >= expected
        if query_filter.operator == "in":
            return isinstance(expected, list) and value in expected
        if query_filter.operator == "contains":
            return str(expected).casefold() in str(value).casefold()
    except (TypeError, ValueError):
        return False
    return False


def _sort_value(value: Any, value_type: str) -> Any | None:
    if value_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if value_type == "boolean":
        return value if isinstance(value, bool) else None
    if value_type == "datetime":
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.timestamp()
        except (TypeError, ValueError):
            return None
    return str(value).casefold()


def _sort_rows(
    rows: list[dict[str, Any]],
    sorts: list[QuerySort],
    definitions: dict[str, dict[str, Any]],
) -> None:
    for sort in reversed(sorts):
        value_type = (
            "string"
            if sort.field in _RESERVED_FIELDS
            else _value_type(definitions[sort.field])
        )
        sortable = [
            (row, _sort_value(row.get(sort.field), value_type))
            for row in rows
            if row.get(sort.field) is not None
        ]
        valid = [(row, value) for row, value in sortable if value is not None]
        invalid = [row for row, value in sortable if value is None]
        missing = [row for row in rows if row.get(sort.field) is None]
        valid.sort(
            key=lambda row: (
                row[1],
                str(row[0].get("id")),
            ),
            reverse=sort.direction == "desc",
        )
        rows[:] = [row for row, _ in valid] + invalid + missing


def _default_project(
    principal: Principal,
    conn: Any,
    object_type: str,
    object_id: str,
    props: dict[str, Any],
    schema: list[dict[str, Any]],
) -> dict[str, Any]:
    redacted = apply_field_redaction(
        principal,
        {"id": object_id, "type": object_type, **props},
        schema,
        conn=conn,
    )
    return redact_ecommerce_pii(redacted)


class CanonicalSemanticReadAdapter:
    def __init__(
        self,
        *,
        connect_factory=None,
        assert_visible: Callable[..., None] = assert_object_type_visible,
        can_access: Callable[..., bool] = can_access_object,
        project: Callable[..., dict[str, Any]] = _default_project,
        markings_for: Callable[..., list[str]] = effective_markings,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._assert_visible = assert_visible
        self._can_access = can_access
        self._project = project
        self._markings_for = markings_for

    def execute(
        self,
        scope: TenantScope,
        principal: Principal,
        request: SemanticQueryRequest,
    ) -> AdapterResult:
        with self._connect_factory(scope) as conn:
            self._assert_visible(conn, scope, request.object_type)
            schema_row = conn.execute(
                "SELECT id,name,properties FROM meta_object_type WHERE id=%s",
                (request.object_type,),
            ).fetchone()
            if schema_row is None:
                raise CanonicalAdapterBlocked(
                    code="OBJECT_TYPE_UNAVAILABLE",
                    message="installed Object Type schema is unavailable",
                )
            schema = list(schema_row["properties"] or [])
            definitions = {
                name: value
                for value in schema
                if (name := _property_name(value)) is not None
            }
            allowed = set(definitions) | _RESERVED_FIELDS
            requested_fields = {
                item.field for item in [*request.filters, *request.sort]
            }
            unknown = sorted(requested_fields - allowed)
            if unknown:
                raise CanonicalAdapterBlocked(
                    code="OBJECT_FIELD_UNAVAILABLE",
                    message=f"fields are not in the installed schema: {','.join(unknown)}",
                )
            selection = self._selection(request)
            rows = conn.execute(
                """SELECT external_id,properties,source_updated_at,payload_hash
                   FROM ecom_object
                   WHERE org_id=%s AND workspace_id=%s AND object_type=%s
                     AND deleted_at IS NULL AND source_updated_at<=%s
                   ORDER BY external_id LIMIT %s""",
                (*scope.key, request.object_type, request.cutoff_at, MAX_SEMANTIC_SOURCE_ROWS + 1),
            ).fetchall()
            if len(rows) > MAX_SEMANTIC_SOURCE_ROWS:
                raise CanonicalAdapterBlocked(
                    code="SEMANTIC_SOURCE_LIMIT_EXCEEDED",
                    message="canonical object source exceeds the bounded read limit",
                )
            projected: list[tuple[dict[str, Any], Any, list[str]]] = []
            for row in rows:
                if row["source_updated_at"] > request.cutoff_at:
                    continue
                object_id = str(row["external_id"])
                if selection and object_id not in selection:
                    continue
                if selection and selection[object_id] != row["payload_hash"]:
                    raise CanonicalAdapterBlocked(
                        code="SELECTION_REFERENCE_DRIFT",
                        message=f"selection revision drifted for {request.object_type}/{object_id}",
                    )
                if not self._can_access(
                    principal, conn, request.object_type, object_id
                ):
                    continue
                item = self._project(
                    principal,
                    conn,
                    request.object_type,
                    object_id,
                    dict(row["properties"] or {}),
                    schema,
                )
                if all(_matches(item.get(f.field), f) for f in request.filters):
                    markings = self._markings_for(
                        conn, scope, request.object_type, object_id
                    ) or ["public"]
                    projected.append((item, row, markings))
        values = [item for item, _, _ in projected]
        _sort_rows(values, request.sort, definitions)
        by_id = {str(item["id"]): (row, markings) for item, row, markings in projected}
        values = values[: request.page_size]
        schema_hash = _canonical_hash(dict(schema_row))
        sources = [
            QuerySourceRef(
                ref=ResourceRef(
                    resource_type="ObjectTypeRevision",
                    resource_id=request.object_type,
                    revision=schema_hash,
                    authority="ontology",
                ),
                content_hash=schema_hash,
                cutoff_at=request.cutoff_at,
                freshness="fresh",
                markings=["public"],
            )
        ]
        for item in values:
            row, markings = by_id[str(item["id"])]
            sources.append(
                QuerySourceRef(
                    ref=ResourceRef(
                        resource_type="EcommerceObjectRevision",
                        resource_id=f"{request.object_type}/{item['id']}",
                        revision=row["payload_hash"],
                        authority="ecom_object",
                    ),
                    content_hash=row["payload_hash"],
                    cutoff_at=row["source_updated_at"],
                    freshness="fresh",
                    markings=markings,
                )
            )
        property_columns = [
            name
            for name in definitions
            if any(name in item for item in values)
        ]
        columns = [
            QueryColumn(key="objectId", label="对象 ID", value_type="string"),
            *[
                QueryColumn(
                    key=name,
                    label=str(definitions[name].get("label") or name),
                    value_type=_value_type(definitions[name]),
                )
                for name in property_columns
            ],
        ]
        query_rows = [
            QueryRow(
                row_id=f"{request.object_type}/{item['id']}",
                values={
                    "objectId": str(item["id"]),
                    **{name: item.get(name) for name in property_columns},
                },
            )
            for item in values
        ]
        return AdapterResult(
            status=(
                AnalystQueryStatus.COMPLETE
                if query_rows
                else AnalystQueryStatus.EMPTY
            ),
            columns=columns,
            rows=query_rows,
            source_refs=sources,
            lineage_refs=[],
            uncertainties=[],
        )

    @staticmethod
    def _selection(request: SemanticQueryRequest) -> dict[str, str]:
        selected: dict[str, str] = {}
        for ref in request.selection_refs:
            prefix = f"{request.object_type}/"
            if (
                ref.resource_type != "EcommerceObjectRevision"
                or ref.authority != "ecom_object"
                or not ref.resource_id.startswith(prefix)
                or not ref.revision
            ):
                raise CanonicalAdapterBlocked(
                    code="SELECTION_REFERENCE_INVALID",
                    message="semantic selection requires exact ecom object revisions",
                )
            object_id = ref.resource_id[len(prefix) :]
            if object_id in selected and selected[object_id] != ref.revision:
                raise CanonicalAdapterBlocked(
                    code="SELECTION_REFERENCE_INVALID",
                    message="semantic selection contains conflicting revisions",
                )
            selected[object_id] = ref.revision
        return selected


class CanonicalKnowledgeReadAdapter:
    def __init__(self, service: AipMemoryKnowledgeSearch) -> None:
        self._service = service

    def execute(
        self,
        scope: TenantScope,
        principal: Principal,
        request: KnowledgeQueryRequest,
    ) -> AdapterResult:
        result = self._service.search(
            scope,
            KnowledgeSearch(
                query=request.query,
                task_id=request.task_ref.resource_id,
                skill_ref=request.skill_ref,
                time_cutoff=request.cutoff_at,
                markings=request.markings,
                limit=min(50, len(request.selection_refs) or 10),
                max_tokens=request.max_tokens,
            ),
            authorized_markings=principal.markings,
            required_applicability=[f"skill:{request.skill_ref.resource_id}"],
        )
        if result.status == "blocked" or not result.matches:
            reasons = ",".join(result.blocked_reasons or ["knowledge_not_found"])
            raise CanonicalAdapterBlocked(
                code="KNOWLEDGE_AUTHORITY_BLOCKED",
                message=f"governed knowledge search blocked: {reasons}",
                retryable=True,
            )
        sources: list[QuerySourceRef] = []
        rows: list[QueryRow] = []
        for match in result.matches:
            citation = match.citation
            observed_at = citation.source.observed_at
            if observed_at > request.cutoff_at:
                raise CanonicalAdapterBlocked(
                    code="KNOWLEDGE_CUTOFF_DRIFT",
                    message="knowledge citation exceeds the requested cutoff",
                )
            sources.append(
                QuerySourceRef(
                    ref=ResourceRef(
                        resource_type="MemoryItemRevision",
                        resource_id=citation.memory_item_id,
                        revision=str(citation.revision),
                        authority="aip-memory",
                    ),
                    content_hash=citation.content_hash,
                    cutoff_at=observed_at,
                    freshness=(
                        "fresh" if citation.freshness == "active" else "stale"
                    ),
                    markings=citation.markings,
                )
            )
            rows.append(
                QueryRow(
                    row_id=f"{citation.memory_item_id}@{citation.revision}",
                    values={
                        "content": match.chunk.content,
                        "score": match.score,
                        "memoryItemId": citation.memory_item_id,
                    },
                )
            )
        uncertainties = list(result.blocked_reasons)
        if result.status == "degraded" and not uncertainties:
            uncertainties = ["knowledge_search_degraded"]
        return AdapterResult(
            status=(
                AnalystQueryStatus.DEGRADED
                if result.status == "degraded"
                else AnalystQueryStatus.COMPLETE
            ),
            columns=[
                QueryColumn(key="content", label="知识内容", value_type="string"),
                QueryColumn(key="score", label="相关度", value_type="number"),
                QueryColumn(
                    key="memoryItemId", label="知识条目", value_type="string"
                ),
            ],
            rows=rows,
            source_refs=sources,
            lineage_refs=[],
            uncertainties=uncertainties,
        )


__all__ = ["CanonicalKnowledgeReadAdapter", "CanonicalSemanticReadAdapter"]
