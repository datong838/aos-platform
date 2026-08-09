"""O1-UX3 tenant-authoritative GraphSnapshot queries over ecom Object/Link."""

from __future__ import annotations

import base64
import hashlib
import json
from collections import deque
from datetime import UTC, datetime
from typing import Any

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_explorer_contracts import GraphQueryDTO, GraphSnapshotDTO
from aos_api.tenant_scope import TenantScope


MAX_SOURCE_OBJECTS = 10_000
MAX_SOURCE_EDGES = 20_000
OPERATIONAL_TYPES = {
    "Knowledge": "knowledge",
    "ActionType": "action_type",
    "ActionInstance": "action_instance",
    "Task": "task",
    "Plan": "plan",
    "Checkpoint": "checkpoint",
    "Artifact": "artifact",
    "Eval": "eval",
    "Evidence": "evidence",
    "RetentionPolicy": "retention_policy",
}


def _node_key(object_type: str, object_id: str) -> str:
    return f"{object_type}:{object_id}"


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _encode_cursor(*, offset: int, query_hash: str, watermark: str) -> str:
    body = {"v": 1, "offset": offset, "queryHash": query_hash, "watermark": watermark}
    body["checksum"] = _hash(body)
    return base64.urlsafe_b64encode(_canonical_json(body).encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(value: str, *, query_hash: str, watermark: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        body = json.loads(raw.decode("utf-8"))
        checksum = body.pop("checksum")
        valid = (
            body == {"v": 1, "offset": body.get("offset"), "queryHash": query_hash, "watermark": watermark}
            and isinstance(body["offset"], int)
            and body["offset"] >= 0
            and checksum == _hash(body)
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        valid = False
        body = {}
    if not valid:
        raise ApiError(code="GRAPH_QUERY_INVALID", message="graph cursor is invalid or stale", status_code=400)
    return int(body["offset"])


class AuthoritativeGraphService:
    """Build deterministic, bounded graph snapshots from scoped ecom tables."""

    def metadata(self, scope: TenantScope) -> dict[str, Any]:
        with connect(scope) as conn:
            counts = conn.execute(
                "SELECT (SELECT count(*) FROM ecom_object WHERE org_id=%s AND workspace_id=%s "
                "AND deleted_at IS NULL) AS objects,(SELECT count(*) FROM ecom_link WHERE org_id=%s "
                "AND workspace_id=%s AND deleted_at IS NULL) AS edges",
                (*scope.key, *scope.key),
            ).fetchone()
            watermarks = conn.execute(
                "SELECT max(value) AS watermark FROM ("
                "SELECT max(updated_at) AS value FROM ecom_object WHERE org_id=%s AND workspace_id=%s "
                "UNION ALL SELECT max(updated_at) AS value FROM ecom_link WHERE org_id=%s AND workspace_id=%s) q",
                (*scope.key, *scope.key),
            ).fetchone()
            schema_rows = conn.execute("SELECT id,name,properties FROM meta_object_type ORDER BY id").fetchall()
        return {
            "objects": int(counts["objects"]),
            "edges": int(counts["edges"]),
            "watermark": watermarks["watermark"].isoformat() if watermarks["watermark"] else "empty",
            "schemaEtag": f"composed-schema-v1:sha256:{_hash([dict(row) for row in schema_rows])}",
        }

    def query(self, scope: TenantScope, request: GraphQueryDTO) -> GraphSnapshotDTO:
        if len(request.graphDomains) != 1:
            raise ApiError(
                code="GRAPH_QUERY_INVALID",
                message="query one graphDomain per GraphSnapshot and compose layers in the client",
                status_code=400,
            )
        graph_domain = request.graphDomains[0]
        graph = (
            self._load_domain(scope, relation_types=request.relationTypes)
            if graph_domain == "domain"
            else self._load_operational(scope, relation_types=request.relationTypes)
        )
        seed_keys = [_node_key(seed.objectType, seed.objectId) for seed in request.seeds]
        missing = [key for key in seed_keys if key not in graph["nodes"]]
        if missing:
            raise ApiError(
                code="OBJECT_REFERENCE_UNSTABLE",
                message=f"canonical graph seed not found: {missing[0]}",
                status_code=404,
            )

        allowed_types = set(request.objectTypes)
        if allowed_types and any(graph["nodes"][key]["object_type"] not in allowed_types for key in seed_keys):
            raise ApiError(
                code="GRAPH_QUERY_INVALID",
                message="objectTypes filter excludes a seed",
                status_code=400,
            )

        depths = self._bfs(
            graph,
            seed_keys=seed_keys,
            hops=request.hops,
            direction=request.direction,
            allowed_types=allowed_types,
        )
        ordered_keys = sorted(depths, key=lambda key: (depths[key], key))
        query_hash = _hash({
            **request.model_dump(mode="json", exclude={"cursor"}),
            "scope": scope.key,
        })
        offset = _decode_cursor(
            request.cursor, query_hash=query_hash, watermark=graph["watermark"]
        ) if request.cursor else 0
        if offset > len(ordered_keys):
            raise ApiError(code="GRAPH_QUERY_INVALID", message="graph cursor offset is out of range", status_code=400)
        page_keys = ordered_keys[offset: offset + request.maxNodes]
        selected = set(page_keys)
        truncated = offset + len(page_keys) < len(ordered_keys)
        next_cursor = _encode_cursor(
            offset=offset + len(page_keys), query_hash=query_hash, watermark=graph["watermark"]
        ) if truncated else None

        nodes = [
            {
                "key": key,
                "objectType": graph["nodes"][key]["object_type"],
                "objectId": graph["nodes"][key]["external_id"],
                "label": f"{graph['nodes'][key]['object_type']} · {graph['nodes'][key]['external_id']}",
                "depth": depths[key],
                "masked": True,
            }
            for key in page_keys
        ]
        edges = []
        for edge in graph["edges"]:
            if edge["source"] not in selected or edge["target"] not in selected:
                continue
            direction = "out" if depths[edge["source"]] <= depths[edge["target"]] else "in"
            edges.append({
                "key": edge["key"],
                "relationType": edge["relation_type"],
                "source": edge["source"],
                "target": edge["target"],
                "direction": direction,
                "graphDomain": graph_domain,
                "edgeAuthority": "authoritative",
                "sourceRevision": edge["payload_hash"],
                "validity": {"validFrom": edge["source_updated_at"], "validUntil": None},
                "evidenceRefs": [],
            })

        return GraphSnapshotDTO.model_validate({
            "scope": {"orgId": scope.org_id, "workspaceId": scope.project_id},
            "sourceAuthority": graph["source_authority"],
            "graphDomain": graph_domain,
            "schemaEtag": graph["schema_etag"],
            "snapshot": {"asOf": datetime.now(UTC).isoformat(), "watermark": graph["watermark"]},
            "nodes": nodes,
            "edges": edges,
            "page": {"truncated": truncated, "nextCursor": next_cursor},
            "limits": {"maxNodes": request.maxNodes, "maxHops": request.hops},
        })

    def shortest_path(
        self,
        scope: TenantScope,
        *,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        max_hops: int,
        relation_types: list[str] | None = None,
    ) -> dict[str, Any]:
        graph = self._load_domain(scope, relation_types=relation_types or [])
        source = _node_key(source_type, source_id)
        target = _node_key(target_type, target_id)
        if source not in graph["nodes"] or target not in graph["nodes"]:
            return {"found": False, "distance": -1, "path": [], "explored": 0, "watermark": graph["watermark"]}
        queue: deque[str] = deque([source])
        previous: dict[str, str | None] = {source: None}
        distance = {source: 0}
        while queue:
            current = queue.popleft()
            if current == target:
                break
            if distance[current] >= max_hops:
                continue
            for neighbor, _ in sorted(graph["both"].get(current, []), key=lambda pair: pair[0]):
                if neighbor not in previous:
                    previous[neighbor] = current
                    distance[neighbor] = distance[current] + 1
                    queue.append(neighbor)
        if target not in previous:
            return {
                "found": False, "distance": -1, "path": [], "explored": len(previous),
                "watermark": graph["watermark"],
            }
        path = []
        cursor: str | None = target
        while cursor is not None:
            node = graph["nodes"][cursor]
            path.append({"type": node["object_type"], "id": node["external_id"], "key": cursor})
            cursor = previous[cursor]
        path.reverse()
        return {
            "found": True, "distance": len(path) - 1, "path": path,
            "explored": len(previous), "watermark": graph["watermark"],
            "sourceAuthority": "ecom_authoritative",
        }

    def _bfs(
        self,
        graph: dict[str, Any],
        *,
        seed_keys: list[str],
        hops: int,
        direction: str,
        allowed_types: set[str],
    ) -> dict[str, int]:
        depths = {key: 0 for key in seed_keys}
        queue: deque[str] = deque(seed_keys)
        adjacency = graph[direction]
        while queue:
            current = queue.popleft()
            if depths[current] >= hops:
                continue
            for neighbor, _ in sorted(adjacency.get(current, []), key=lambda pair: pair[0]):
                node = graph["nodes"].get(neighbor)
                if node is None or (allowed_types and node["object_type"] not in allowed_types):
                    continue
                if neighbor not in depths:
                    depths[neighbor] = depths[current] + 1
                    queue.append(neighbor)
        return depths

    def _load_domain(self, scope: TenantScope, *, relation_types: list[str]) -> dict[str, Any]:
        relation_filter = " AND link_type=ANY(%s)" if relation_types else ""
        relation_params: tuple[object, ...] = (relation_types,) if relation_types else ()
        with connect(scope) as conn:
            objects = conn.execute(
                "SELECT object_type,external_id,updated_at FROM ecom_object "
                "WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL "
                "ORDER BY object_type,external_id LIMIT %s",
                (*scope.key, MAX_SOURCE_OBJECTS + 1),
            ).fetchall()
            edges = conn.execute(
                "SELECT link_type,source_object_type,source_external_id,target_object_type,target_external_id,"
                "source_updated_at,payload_hash,updated_at FROM ecom_link "
                "WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL"
                f"{relation_filter} ORDER BY link_type,source_object_type,source_external_id,target_object_type,target_external_id LIMIT %s",
                (*scope.key, *relation_params, MAX_SOURCE_EDGES + 1),
            ).fetchall()
            schema_rows = conn.execute(
                "SELECT id,name,properties FROM meta_object_type ORDER BY id"
            ).fetchall()
        if len(objects) > MAX_SOURCE_OBJECTS or len(edges) > MAX_SOURCE_EDGES:
            raise ApiError(
                code="GRAPH_QUERY_TOO_LARGE",
                message="authoritative graph exceeds the server source budget",
                status_code=413,
            )
        if not objects:
            raise ApiError(
                code="GRAPH_AUTHORITY_UNAVAILABLE",
                message="no installed authoritative ecommerce graph is available for this workspace",
                status_code=409,
            )

        nodes = {
            _node_key(row["object_type"], row["external_id"]): {
                "object_type": row["object_type"], "external_id": row["external_id"],
                "updated_at": row["updated_at"].isoformat(),
            }
            for row in objects
        }
        edge_rows = []
        outgoing: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        incoming: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        both: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for row in edges:
            source = _node_key(row["source_object_type"], row["source_external_id"])
            target = _node_key(row["target_object_type"], row["target_external_id"])
            if source not in nodes or target not in nodes:
                continue
            edge = {
                "key": _hash({
                    "relationType": row["link_type"], "source": source, "target": target,
                    "payloadHash": row["payload_hash"],
                }),
                "relation_type": row["link_type"], "source": source, "target": target,
                "source_updated_at": row["source_updated_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(), "payload_hash": row["payload_hash"],
            }
            edge_rows.append(edge)
            outgoing.setdefault(source, []).append((target, edge))
            incoming.setdefault(target, []).append((source, edge))
            both.setdefault(source, []).append((target, edge))
            both.setdefault(target, []).append((source, edge))
        watermark = max(
            [node["updated_at"] for node in nodes.values()]
            + [edge["updated_at"] for edge in edge_rows],
        )
        schema_etag = f"composed-schema-v1:sha256:{_hash([dict(row) for row in schema_rows])}"
        return {
            "nodes": nodes, "edges": edge_rows, "out": outgoing, "in": incoming, "both": both,
            "watermark": watermark, "schema_etag": schema_etag,
            "source_authority": "ecom_authoritative",
        }

    def _load_operational(self, scope: TenantScope, *, relation_types: list[str]) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        rows_by_type: dict[str, list[dict[str, Any]]] = {}
        with connect(scope) as conn:
            for object_type, kind in OPERATIONAL_TYPES.items():
                rows = conn.execute(
                    f"SELECT h.record_id,h.updated_at,r.payload,r.payload_hash,r.created_at "
                    f"FROM ontology_{kind}_head h JOIN ontology_{kind}_revision r ON "
                    "r.org_id=h.org_id AND r.workspace_id=h.workspace_id AND r.record_id=h.record_id "
                    "AND r.revision=h.active_revision WHERE h.org_id=%s AND h.workspace_id=%s "
                    "AND h.archived_at IS NULL ORDER BY h.record_id LIMIT %s",
                    (*scope.key, MAX_SOURCE_OBJECTS + 1),
                ).fetchall()
                if len(rows) > MAX_SOURCE_OBJECTS:
                    raise ApiError(
                        code="GRAPH_QUERY_TOO_LARGE",
                        message="operational lineage exceeds the server source budget",
                        status_code=413,
                    )
                normalized = [dict(row) for row in rows]
                rows_by_type[object_type] = normalized
                for row in normalized:
                    key = _node_key(object_type, row["record_id"])
                    nodes[key] = {
                        "object_type": object_type,
                        "external_id": row["record_id"],
                        "updated_at": row["updated_at"].isoformat(),
                    }
        if len(nodes) > MAX_SOURCE_OBJECTS:
            raise ApiError(
                code="GRAPH_QUERY_TOO_LARGE",
                message="operational lineage exceeds the server source budget",
                status_code=413,
            )
        if not nodes:
            raise ApiError(
                code="GRAPH_AUTHORITY_UNAVAILABLE",
                message="no operational lineage is available for this workspace",
                status_code=409,
            )

        edge_rows: list[dict[str, Any]] = []
        allowed_relations = set(relation_types)

        def ref_id(value: object) -> str | None:
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, dict):
                for field in ("recordId", "taskId", "evidenceId", "id"):
                    candidate = value.get(field)
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate
            return None

        def add_edge(
            source_type: str,
            source_id: str,
            relation_type: str,
            target_type: str,
            target_value: object,
            row: dict[str, Any],
        ) -> None:
            target_id = ref_id(target_value)
            if target_id is None or (allowed_relations and relation_type not in allowed_relations):
                return
            source = _node_key(source_type, source_id)
            target = _node_key(target_type, target_id)
            if source not in nodes or target not in nodes:
                return
            edge_rows.append({
                "key": _hash({
                    "relationType": relation_type, "source": source, "target": target,
                    "payloadHash": row["payload_hash"],
                }),
                "relation_type": relation_type,
                "source": source,
                "target": target,
                "source_updated_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
                "payload_hash": row["payload_hash"],
            })

        for object_type, rows in rows_by_type.items():
            for row in rows:
                payload = row["payload"] if isinstance(row["payload"], dict) else {}
                record_id = row["record_id"]
                if object_type == "Plan":
                    add_edge(object_type, record_id, "Plan.forTask", "Task", payload.get("taskRef"), row)
                elif object_type == "Checkpoint":
                    add_edge(object_type, record_id, "Checkpoint.forTask", "Task", payload.get("taskRef"), row)
                    add_edge(object_type, record_id, "Checkpoint.forPlan", "Plan", payload.get("planRef"), row)
                elif object_type == "Artifact":
                    add_edge(object_type, record_id, "Artifact.forTask", "Task", payload.get("taskRef"), row)
                elif object_type == "Eval":
                    add_edge(object_type, record_id, "Eval.forTask", "Task", payload.get("taskRef"), row)
                    for evidence in payload.get("evidenceRefs", []):
                        add_edge(object_type, record_id, "Eval.supportedBy", "Evidence", evidence, row)
                elif object_type == "ActionInstance":
                    add_edge(
                        object_type, record_id, "ActionInstance.ofType", "ActionType",
                        payload.get("actionTypeRef"), row,
                    )
                    add_edge(object_type, record_id, "ActionInstance.forTask", "Task", payload.get("taskRef"), row)
                    for evidence in payload.get("evidenceRefs", []):
                        add_edge(object_type, record_id, "ActionInstance.supportedBy", "Evidence", evidence, row)
                elif object_type == "ActionType":
                    add_edge(
                        object_type, record_id, "ActionType.compensatedBy", "ActionType",
                        payload.get("compensationActionType"), row,
                    )

        if len(edge_rows) > MAX_SOURCE_EDGES:
            raise ApiError(
                code="GRAPH_QUERY_TOO_LARGE",
                message="operational lineage exceeds the server edge budget",
                status_code=413,
            )
        outgoing: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        incoming: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        both: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for edge in edge_rows:
            outgoing.setdefault(edge["source"], []).append((edge["target"], edge))
            incoming.setdefault(edge["target"], []).append((edge["source"], edge))
            both.setdefault(edge["source"], []).append((edge["target"], edge))
            both.setdefault(edge["target"], []).append((edge["source"], edge))
        watermark = max(node["updated_at"] for node in nodes.values())
        schema_etag = f"operational-lineage-v1:sha256:{_hash(sorted(OPERATIONAL_TYPES.items()))}"
        return {
            "nodes": nodes,
            "edges": edge_rows,
            "out": outgoing,
            "in": incoming,
            "both": both,
            "watermark": watermark,
            "schema_etag": schema_etag,
            "source_authority": "operational_authoritative",
        }


_service = AuthoritativeGraphService()


def get_authoritative_graph_service() -> AuthoritativeGraphService:
    return _service
