"""Canonical, tenant-neutral data contract for the AIP Logic canvas graph."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_GRAPH_NODES = 300
MAX_GRAPH_EDGES = 1200
MAX_GRAPH_JSON_BYTES = 1_048_576
MAX_NODE_CONFIG_BYTES = 131_072

LogicBlockKind = Literal[
    "input",
    "create_variable",
    "get_property",
    "use_llm",
    "use_tool",
    "transform",
    "apply_action",
    "execute",
    "branch",
    "handoff",
]
LogicGraphStatus = Literal["draft", "published", "archived"]
LogicGraphWriteStatus = Literal["draft", "archived"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LogicGraphNode(_StrictModel):
    id: str = Field(min_length=1, max_length=160)
    kind: LogicBlockKind
    label: str = Field(min_length=1, max_length=240)
    position_x: float = Field(default=0.0, ge=0)
    position_y: float = Field(default=0.0, ge=0)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", "label")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("position_x", "position_y")
    @classmethod
    def _finite_position(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("position must be finite")
        return value


class LogicGraphEdge(_StrictModel):
    id: str = Field(min_length=1, max_length=160)
    source_node_id: str = Field(min_length=1, max_length=160)
    source_port: str = Field(default="out", min_length=1, max_length=80)
    target_node_id: str = Field(min_length=1, max_length=160)
    target_port: str = Field(default="in", min_length=1, max_length=80)
    branch_path: str = Field(default="", max_length=160)
    order: int = Field(default=0, ge=0)

    @field_validator("id", "source_node_id", "target_node_id")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("source_port", "target_port")
    @classmethod
    def _port_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("port must not be blank")
        return normalized

    @field_validator("branch_path")
    @classmethod
    def _normalize_branch_path(cls, value: str) -> str:
        return value.strip()


class LogicGraphContent(_StrictModel):
    name: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=4000)
    status: LogicGraphWriteStatus = "draft"
    schema_version: int = Field(default=1, ge=1)
    nodes: list[LogicGraphNode] = Field(default_factory=list, max_length=MAX_GRAPH_NODES)
    edges: list[LogicGraphEdge] = Field(default_factory=list, max_length=MAX_GRAPH_EDGES)
    entry_node_ids: list[str] = Field(default_factory=list, max_length=MAX_GRAPH_NODES)

    @field_validator("name")
    @classmethod
    def _name_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("entry_node_ids")
    @classmethod
    def _normalize_entry_ids(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            entry_id = value.strip()
            if not entry_id:
                raise ValueError("entry node id must not be blank")
            if len(entry_id) > 160:
                raise ValueError("entry node id exceeds 160 characters")
            normalized.append(entry_id)
        return normalized


class CreateLogicGraphRequest(LogicGraphContent):
    id: str | None = Field(default=None, min_length=1, max_length=160)

    @field_validator("id")
    @classmethod
    def _normalize_graph_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("id must not be blank")
        return normalized


class ReplaceLogicGraphRequest(LogicGraphContent):
    expected_revision: int = Field(ge=1)


class ValidateLogicGraphRequest(LogicGraphContent):
    pass


class LogicGraphSnapshot(_StrictModel):
    id: str
    name: str
    description: str
    status: LogicGraphStatus
    schema_version: int
    revision: int
    published_version: int | None = None
    graph_hash: str
    nodes: list[LogicGraphNode]
    edges: list[LogicGraphEdge]
    entry_node_ids: list[str]
    created_at: datetime
    updated_at: datetime
    persisted: bool = True


class LogicGraphValidationIssue(_StrictModel):
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    field: str | None = None


class LogicGraphValidationResult(_StrictModel):
    valid: bool
    graph_hash: str
    issues: list[LogicGraphValidationIssue] = Field(default_factory=list)


class LogicGraphValidationError(ValueError):
    def __init__(self, issues: list[LogicGraphValidationIssue]) -> None:
        self.issues = issues
        super().__init__("logic graph validation failed")


def logic_graph_content_payload(content: LogicGraphContent) -> dict[str, Any]:
    return {
        "name": content.name,
        "description": content.description,
        "status": content.status,
        "schema_version": content.schema_version,
        "nodes": [node.model_dump(mode="json") for node in content.nodes],
        "edges": [edge.model_dump(mode="json") for edge in content.edges],
        "entry_node_ids": list(content.entry_node_ids),
    }


def compute_logic_graph_hash(content: LogicGraphContent) -> str:
    return compute_logic_graph_payload_hash(logic_graph_content_payload(content))


def compute_logic_graph_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_size(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def validate_logic_graph(content: LogicGraphContent) -> LogicGraphValidationResult:
    issues: list[LogicGraphValidationIssue] = []
    graph_hash = compute_logic_graph_hash(content)

    if _json_size(logic_graph_content_payload(content)) > MAX_GRAPH_JSON_BYTES:
        issues.append(
            LogicGraphValidationIssue(
                code="GRAPH_TOO_LARGE",
                message=f"graph JSON exceeds {MAX_GRAPH_JSON_BYTES} bytes",
            )
        )

    node_ids: set[str] = set()
    node_kinds: dict[str, LogicBlockKind] = {}
    branch_paths: dict[str, set[str]] = {}
    for node in content.nodes:
        if node.id in node_ids:
            issues.append(
                LogicGraphValidationIssue(
                    code="DUPLICATE_NODE_ID",
                    message=f"duplicate node id: {node.id}",
                    node_id=node.id,
                    field="nodes",
                )
            )
        else:
            node_ids.add(node.id)
            node_kinds[node.id] = node.kind
        if _json_size(node.config) > MAX_NODE_CONFIG_BYTES:
            issues.append(
                LogicGraphValidationIssue(
                    code="NODE_CONFIG_TOO_LARGE",
                    message=f"node config exceeds {MAX_NODE_CONFIG_BYTES} bytes",
                    node_id=node.id,
                    field="config",
                )
            )
        if node.kind == "branch":
            raw_paths = node.config.get("paths")
            declared: set[str] = set()
            default_count = 0
            if not isinstance(raw_paths, list) or not raw_paths:
                issues.append(
                    LogicGraphValidationIssue(
                        code="BRANCH_PATHS_REQUIRED",
                        message=f"branch {node.id} requires a non-empty config.paths list",
                        node_id=node.id,
                        field="config.paths",
                    )
                )
            else:
                for raw_path in raw_paths:
                    path_id = ""
                    if isinstance(raw_path, dict):
                        path_id = str(raw_path.get("id") or "").strip()
                    if not path_id or len(path_id) > 80:
                        issues.append(
                            LogicGraphValidationIssue(
                                code="INVALID_BRANCH_PATH",
                                message=f"branch {node.id} path requires a non-empty id up to 80 characters",
                                node_id=node.id,
                                field="config.paths",
                            )
                        )
                        continue
                    if path_id in declared:
                        issues.append(
                            LogicGraphValidationIssue(
                                code="DUPLICATE_BRANCH_PATH",
                                message=f"branch {node.id} has duplicate path id: {path_id}",
                                node_id=node.id,
                                field="config.paths",
                            )
                        )
                    declared.add(path_id)
                    assert isinstance(raw_path, dict)
                    if (
                        raw_path.get("default") is True
                        or raw_path.get("is_default") is True
                        or path_id.lower() == "default"
                    ):
                        default_count += 1
                if default_count > 1:
                    issues.append(
                        LogicGraphValidationIssue(
                            code="BRANCH_MULTIPLE_DEFAULTS",
                            message=f"branch {node.id} has more than one default path",
                            node_id=node.id,
                            field="config.paths",
                        )
                    )
            branch_paths[node.id] = declared

    edge_ids: set[str] = set()
    edge_keys: set[tuple[str, str, str, str, str]] = set()
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    incoming: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for edge in content.edges:
        if edge.id in edge_ids:
            issues.append(
                LogicGraphValidationIssue(
                    code="DUPLICATE_EDGE_ID",
                    message=f"duplicate edge id: {edge.id}",
                    edge_id=edge.id,
                    field="edges",
                )
            )
        edge_ids.add(edge.id)
        key = (
            edge.source_node_id,
            edge.source_port,
            edge.target_node_id,
            edge.target_port,
            edge.branch_path,
        )
        if key in edge_keys:
            issues.append(
                LogicGraphValidationIssue(
                    code="DUPLICATE_EDGE",
                    message=f"duplicate edge: {edge.source_node_id} -> {edge.target_node_id}",
                    edge_id=edge.id,
                    field="edges",
                )
            )
        edge_keys.add(key)

        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            issues.append(
                LogicGraphValidationIssue(
                    code="EDGE_ENDPOINT_NOT_FOUND",
                    message=(
                        f"edge endpoint not found: {edge.source_node_id} -> "
                        f"{edge.target_node_id}"
                    ),
                    edge_id=edge.id,
                    field="edges",
                )
            )
            continue
        if edge.target_port != "in":
            issues.append(
                LogicGraphValidationIssue(
                    code="INVALID_TARGET_PORT",
                    message=f"edge {edge.id} target_port must be in",
                    edge_id=edge.id,
                    node_id=edge.target_node_id,
                    field="target_port",
                )
            )
        source_kind = node_kinds.get(edge.source_node_id)
        if source_kind == "branch":
            if edge.source_port != edge.branch_path:
                issues.append(
                    LogicGraphValidationIssue(
                        code="BRANCH_PATH_PORT_MISMATCH",
                        message=(
                            f"branch edge {edge.id} source_port and branch_path must "
                            "be the same declared path id"
                        ),
                        edge_id=edge.id,
                        node_id=edge.source_node_id,
                        field="source_port",
                    )
                )
            elif edge.branch_path not in branch_paths.get(edge.source_node_id, set()):
                issues.append(
                    LogicGraphValidationIssue(
                        code="BRANCH_PATH_NOT_DECLARED",
                        message=f"branch edge {edge.id} uses an undeclared path id",
                        edge_id=edge.id,
                        node_id=edge.source_node_id,
                        field="branch_path",
                    )
                )
        else:
            if edge.source_port != "out":
                issues.append(
                    LogicGraphValidationIssue(
                        code="INVALID_SOURCE_PORT",
                        message=f"non-branch edge {edge.id} source_port must be out",
                        edge_id=edge.id,
                        node_id=edge.source_node_id,
                        field="source_port",
                    )
                )
            if edge.branch_path:
                issues.append(
                    LogicGraphValidationIssue(
                        code="NON_BRANCH_PATH_NOT_ALLOWED",
                        message=f"non-branch edge {edge.id} must not set branch_path",
                        edge_id=edge.id,
                        node_id=edge.source_node_id,
                        field="branch_path",
                    )
                )
        if edge.source_node_id == edge.target_node_id:
            issues.append(
                LogicGraphValidationIssue(
                    code="SELF_EDGE",
                    message=f"self edge is not allowed: {edge.source_node_id}",
                    edge_id=edge.id,
                    node_id=edge.source_node_id,
                    field="edges",
                )
            )
            continue
        adjacency[edge.source_node_id].append(edge.target_node_id)
        incoming[edge.target_node_id].add(edge.source_node_id)

    seen_entries: set[str] = set()
    if node_ids and not content.entry_node_ids:
        issues.append(
            LogicGraphValidationIssue(
                code="ENTRY_REQUIRED",
                message="a non-empty logic graph requires at least one entry node",
                field="entry_node_ids",
            )
        )
    for entry_id in content.entry_node_ids:
        if entry_id in seen_entries:
            issues.append(
                LogicGraphValidationIssue(
                    code="DUPLICATE_ENTRY",
                    message=f"duplicate entry node id: {entry_id}",
                    node_id=entry_id,
                    field="entry_node_ids",
                )
            )
        seen_entries.add(entry_id)
        if entry_id not in node_ids:
            issues.append(
                LogicGraphValidationIssue(
                    code="ENTRY_NODE_NOT_FOUND",
                    message=f"entry node not found: {entry_id}",
                    node_id=entry_id,
                    field="entry_node_ids",
                )
            )

    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_found = False

    def visit(node_id: str) -> None:
        nonlocal cycle_found
        if cycle_found or node_id in visited:
            return
        if node_id in visiting:
            cycle_found = True
            return
        visiting.add(node_id)
        for target_id in adjacency[node_id]:
            visit(target_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in node_ids:
        visit(node_id)
    if cycle_found:
        issues.append(
            LogicGraphValidationIssue(
                code="GRAPH_CYCLE",
                message="logic graph must be acyclic",
                field="edges",
            )
        )

    for node_id, kind in node_kinds.items():
        if kind == "handoff" and len(incoming[node_id]) < 2:
            issues.append(
                LogicGraphValidationIssue(
                    code="HANDOFF_REQUIRES_UPSTREAMS",
                    message=f"handoff {node_id} requires at least two distinct upstream nodes",
                    node_id=node_id,
                    field="edges",
                )
            )

    return LogicGraphValidationResult(valid=not issues, graph_hash=graph_hash, issues=issues)


def require_valid_logic_graph(content: LogicGraphContent) -> str:
    result = validate_logic_graph(content)
    if not result.valid:
        raise LogicGraphValidationError(result.issues)
    return result.graph_hash
